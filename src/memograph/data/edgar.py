"""Company financials from SEC EDGAR (free, official US filings), cached for 30 days.

We use the SEC's "company facts" API: every number a company has reported in its
filings, already in structured form, so no PDF or HTML parsing is needed.
"""
from datetime import date

import httpx

from memograph.core.config import settings
from memograph.data.cache import cached
from memograph.data.schemas import FinancialFact, Fundamentals

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Our name for a number -> the accounting tags companies may use for it.
CONCEPTS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": ["StockholdersEquity"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
}


async def _get_json(url: str) -> dict:
    # The SEC requires a User-Agent with a contact email, or it blocks you.
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": settings.edgar_user_agent}) as client:
        r = await client.get(url)
    r.raise_for_status()
    return r.json()


async def lookup_cik(ticker: str) -> tuple[str, str]:
    """'AAPL' -> ('0000320193', 'Apple Inc.')"""
    data = await cached("edgar", "company_tickers", lambda: _get_json(TICKERS_URL))
    for row in data.values():
        if row["ticker"].upper() == ticker.upper():
            return str(row["cik_str"]).zfill(10), row["title"]
    raise ValueError(f"Ticker {ticker} not found on SEC EDGAR")


def latest_annual(facts_json: dict, tags: list[str], before: date | None = None) -> FinancialFact | None:
    """The most recent full-year value for any of `tags`, from a 10-K filed before `before`."""
    us_gaap = facts_json.get("facts", {}).get("us-gaap", {})
    best: FinancialFact | None = None
    for tag in tags:
        for unit, rows in us_gaap.get(tag, {}).get("units", {}).items():
            for r in rows:
                if r.get("form") != "10-K" or r.get("fp") != "FY":
                    continue
                if before and date.fromisoformat(r["filed"]) >= before:
                    continue  # filed after our decision date: would be looking into the future
                if "start" in r and (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days < 300:
                    continue  # a quarter reported inside the yearly filing, not the full year
                cand = FinancialFact(value=r["val"], unit=unit, period_end=r["end"], form=r["form"], filed=r["filed"])
                if best is None or (cand.period_end, cand.filed) > (best.period_end, best.filed):
                    best = cand
    return best


async def get_fundamentals(ticker: str, before: date | None = None) -> Fundamentals:
    cik, name = await lookup_cik(ticker)

    async def fetch() -> dict:
        raw = await _get_json(FACTS_URL.format(cik=cik))
        facts = {}
        for our_name, tags in CONCEPTS.items():
            fact = latest_annual(raw, tags, before)
            if fact:
                facts[our_name] = fact.model_dump(mode="json")
        return {"ticker": ticker.upper(), "cik": cik, "company_name": name, "facts": facts}

    payload = await cached("edgar", f"facts:{cik}:{before or 'latest'}", fetch)
    return Fundamentals(**payload)
