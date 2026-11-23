"""Official annual reports of EU/UK listed companies, in ESEF format, via filings.xbrl.org.

Since financial year 2020, EU listed companies must publish their annual financial
report as tagged, machine-readable data (ESEF), the European equivalent of SEC XBRL.
filings.xbrl.org (run by XBRL International) collects these filings and offers a
free API, including each filing's publication date.

Steps:
1. ticker -> LEI (the company ID used in EU filings), via ISIN or name on GLEIF
2. LEI -> list of the company's filings on filings.xbrl.org
3. pick the newest filing that was public before our decision date
4. read its xBRL-JSON and pull out the numbers we need (IFRS tags)
"""
import asyncio
import hashlib
import json
from datetime import date, datetime, timedelta

import httpx
import yfinance as yf

from memograph.core.config import settings
from memograph.data.cache import cached
from memograph.data.lei_overrides import LEI_OVERRIDES
from memograph.data.markets import market_for
from memograph.data.schemas import FinancialFact, Fundamentals

FXO = "https://filings.xbrl.org"
GLEIF = "https://api.gleif.org/api/v1/lei-records"
PUBLISH_LAG = timedelta(days=120)  # only used if a filing has no publication date

# Our name -> IFRS tags, in order of preference (first one found wins).
CONCEPTS = {
    "revenue": ["ifrs-full:Revenue", "ifrs-full:RevenueFromContractsWithCustomers"],
    "net_income": ["ifrs-full:ProfitLossAttributableToOwnersOfParent", "ifrs-full:ProfitLoss"],
    "total_assets": ["ifrs-full:Assets"],
    "total_liabilities": ["ifrs-full:Liabilities"],
    "stockholders_equity": ["ifrs-full:EquityAttributableToOwnersOfParent", "ifrs-full:Equity"],
    "long_term_debt": ["ifrs-full:NoncurrentFinancialLiabilities", "ifrs-full:LongtermBorrowings"],
    "cash": ["ifrs-full:CashAndCashEquivalents"],
    "operating_cash_flow": ["ifrs-full:CashFlowsFromUsedInOperatingActivities"],
    "capex": ["ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"],
}
# A fact with any other dimension is a breakdown (by segment, region...), not the group total.
TOTAL_DIMS = {"concept", "entity", "period", "unit", "language"}


async def _get(url: str, params: dict | None = None) -> dict:
    headers = {"User-Agent": settings.edgar_user_agent}  # polite: say who we are
    async with httpx.AsyncClient(timeout=60, headers=headers, follow_redirects=True) as client:
        r = await client.get(url, params=params)
    r.raise_for_status()
    return r.json()


def _abs(url: str) -> str:
    return url if url.startswith("http") else FXO + url


# ---------- 1. ticker -> LEI ----------

def _yahoo_isin_and_name(ticker: str) -> tuple[str | None, str | None]:
    t = yf.Ticker(ticker)
    isin = name = None
    try:
        isin = t.isin
    except Exception:
        pass
    try:
        info = t.info or {}
        name = info.get("longName") or info.get("shortName")
    except Exception:
        pass
    return (isin if isin and len(isin) == 12 else None), name


async def lookup_lei(ticker: str) -> str:
    t = ticker.upper()
    if t in LEI_OVERRIDES:
        return LEI_OVERRIDES[t]

    async def fetch() -> dict:
        isin, name = await asyncio.to_thread(_yahoo_isin_and_name, t)
        if isin:  # most reliable: ISIN is the security's official ID
            data = (await _get(GLEIF, {"filter[isin]": isin})).get("data", [])
            if data:
                return {"lei": data[0]["id"], "via": f"ISIN {isin}"}
        if name:
            for key in ("filter[entity.legalName]", "filter[fulltext]"):  # exact name, then fuzzy
                data = (await _get(GLEIF, {key: name, "page[size]": 1})).get("data", [])
                if data:
                    return {"lei": data[0]["id"], "via": f"name '{name}'"}
        raise ValueError(f"no LEI found for {t}; add it to lei_overrides.py")

    return (await cached("fundamentals", f"lei:{t}", fetch))["lei"]


# ---------- 2 + 3. the company's filings, and which one to use ----------

async def list_filings(lei: str) -> list[dict]:
    async def fetch() -> list[dict]:
        flt = json.dumps([{"name": "entity.identifier", "op": "eq", "val": lei}])
        data = await _get(f"{FXO}/api/filings", {"filter": flt, "include": "entity", "page[size]": 100})
        names = {e["id"]: e.get("attributes", {}).get("name") for e in data.get("included", []) if e.get("type") == "entity"}
        out = []
        for d in data.get("data", []):
            a = d.get("attributes", {})
            if not a.get("json_url") or not a.get("period_end"):
                continue
            ent = (d.get("relationships", {}).get("entity", {}) or {}).get("data") or {}
            published = a.get("published") or a.get("date_added")
            out.append({
                "period_end": a["period_end"][:10],
                "published": published[:10] if published else None,
                "json_url": a["json_url"],
                "viewer_url": a.get("viewer_url"),
                "entity_name": names.get(ent.get("id")),
                "errors": a.get("error_count") or 0,
            })
        if not out:  # raise instead of returning [], so an empty answer is never cached
            raise ValueError(f"filings.xbrl.org returned no usable filings for LEI {lei}")
        return out

    return await cached("fundamentals", f"esef:filings:{lei}", fetch)


def public_date(filing: dict) -> date:
    if filing.get("published"):
        return date.fromisoformat(filing["published"])
    return date.fromisoformat(filing["period_end"]) + PUBLISH_LAG


def pick_filing(filings: list[dict], before: date | None = None) -> dict | None:
    """Newest year that was already public before `before`; among duplicates (e.g. German
    and English versions), the one with the fewest validation errors."""
    best, best_key = None, None
    for f in filings:
        if before and public_date(f) >= before:
            continue  # not public yet on our decision date
        key = (date.fromisoformat(f["period_end"]), -f.get("errors", 0))
        if best_key is None or key > best_key:
            best, best_key = f, key
    return best


# ---------- 4. read the numbers ----------

def _xbrl_date(s: str, is_end: bool) -> date:
    d = datetime.fromisoformat(s.replace("Z", ""))
    # xBRL-JSON writes "end of 31 Dec 2025" as "2026-01-01T00:00:00"
    if is_end and "T" in s and d.time() == datetime.min.time():
        return (d - timedelta(days=1)).date()
    return d.date()


def parse_period(period: str) -> tuple[date | None, date]:
    """'2025-01-01T00:00:00/2026-01-01T00:00:00' -> (2025-01-01, 2025-12-31); an instant -> (None, day)."""
    if "/" in period:
        start, end = period.split("/")
        return _xbrl_date(start, False), _xbrl_date(end, True)
    return None, _xbrl_date(period, True)


def extract_fact(xbrl: dict, concepts: list[str], period_end: date) -> tuple[float, str] | None:
    """Group-total value for the first of `concepts` reported for the year ending `period_end`."""
    facts = xbrl.get("facts", {})
    for concept in concepts:
        for f in facts.values():
            dims = f.get("dimensions", {})
            if dims.get("concept") != concept or set(dims) - TOTAL_DIMS or "period" not in dims:
                continue
            start, end = parse_period(dims["period"])
            if abs((end - period_end).days) > 7:
                continue  # last year's comparison figure, not this year
            if start and (end - start).days < 300:
                continue  # a quarter or half-year, not the full year
            try:
                value = float(f["value"])
            except (KeyError, TypeError, ValueError):
                continue
            return value, (dims.get("unit", "").split(":")[-1] or "?")
    return None


async def get_fundamentals(ticker: str, before: date | None = None) -> Fundamentals:
    t = ticker.upper()
    lei = await lookup_lei(t)
    filing = pick_filing(await list_filings(lei), before)
    if not filing:
        raise ValueError(f"no ESEF filing on filings.xbrl.org for {t} (LEI {lei})")
    period_end = date.fromisoformat(filing["period_end"])

    async def fetch() -> dict:
        xbrl = await _get(_abs(filing["json_url"]))
        found = {}
        for our_name, concepts in CONCEPTS.items():
            hit = extract_fact(xbrl, concepts, period_end)
            if hit:
                value, unit = hit
                found[our_name] = {"value": abs(value) if our_name == "capex" else value, "unit": unit}
        return found

    key = "esef:facts:" + hashlib.sha1(filing["json_url"].encode()).hexdigest()
    found = await cached("fundamentals", key, fetch)
    filed = public_date(filing)
    facts = {
        k: FinancialFact(value=v["value"], unit=v["unit"], period_end=period_end, form="ESEF annual report", filed=filed)
        for k, v in found.items()
    }
    return Fundamentals(
        ticker=t, company_name=filing.get("entity_name") or t, facts=facts,
        source="ESEF via filings.xbrl.org", country=market_for(t).country,
        source_url=_abs(filing["viewer_url"]) if filing.get("viewer_url") else None,
    )
