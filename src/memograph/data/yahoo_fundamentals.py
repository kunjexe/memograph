"""Company financials for non-US companies, from Yahoo Finance annual reports.

SEC EDGAR only covers US companies. Yahoo has yearly income statement, balance
sheet and cash flow for most listed companies worldwide. It is less official
than the SEC and has no filing dates, so we assume a report becomes public
90 days after the year ends (used for the no-look-ahead rule).
"""
import asyncio
from datetime import date, timedelta

import yfinance as yf

from memograph.data.cache import cached
from memograph.data.markets import market_for
from memograph.data.schemas import FinancialFact, Fundamentals

# Our name -> Yahoo's row labels, in order of preference.
LABELS = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "total_assets": ["Total Assets"],
    "total_liabilities": ["Total Liabilities Net Minority Interest"],
    "stockholders_equity": ["Stockholders Equity", "Common Stock Equity"],
    "long_term_debt": ["Long Term Debt"],
    "cash": ["Cash And Cash Equivalents"],
    "operating_cash_flow": ["Operating Cash Flow"],
    "capex": ["Capital Expenditure"],
}
REPORT_LAG = timedelta(days=90)


def latest_from_statements(
    periods: dict[str, dict[str, float | None]], labels: list[str], currency: str, before: date | None = None
) -> FinancialFact | None:
    """periods = {"2025-12-31": {"Total Revenue": 1.2e9, ...}, ...} -> newest usable value."""
    best: FinancialFact | None = None
    for end_iso, rows in periods.items():
        end = date.fromisoformat(end_iso[:10])
        published = end + REPORT_LAG
        if before and published >= before:
            continue  # probably not public yet on our decision date
        for label in labels:
            value = rows.get(label)
            if value is None or value != value:  # missing or NaN
                continue
            cand = FinancialFact(value=value, unit=currency, period_end=end, form="annual report", filed=published)
            if best is None or cand.period_end > best.period_end:
                best = cand
            break
    return best


async def get_fundamentals(ticker: str, before: date | None = None) -> Fundamentals:
    ticker = ticker.upper()

    def fetch_sync() -> dict:
        t = yf.Ticker(ticker)
        info = t.info or {}
        periods: dict[str, dict] = {}
        for df in (t.income_stmt, t.balance_sheet, t.cashflow):
            if df is None or df.empty:
                continue
            for col in df.columns:
                rows = {str(k): (None if v != v else float(v)) for k, v in df[col].items()}
                periods.setdefault(col.date().isoformat(), {}).update(rows)
        if not periods:
            raise ValueError(f"No financial statements on Yahoo for {ticker}")
        return {
            "name": info.get("longName") or info.get("shortName") or ticker,
            "currency": info.get("financialCurrency") or info.get("currency") or "?",
            "periods": periods,
        }

    async def fetch() -> dict:
        return await asyncio.to_thread(fetch_sync)

    raw = await cached("fundamentals", f"yahoo:{ticker}", fetch)
    facts = {}
    for our_name, labels in LABELS.items():
        fact = latest_from_statements(raw["periods"], labels, raw["currency"], before)
        if fact:
            if our_name == "capex":
                fact.value = abs(fact.value)  # Yahoo shows spending as negative; SEC as positive
            facts[our_name] = fact
    return Fundamentals(
        ticker=ticker, company_name=raw["name"], facts=facts,
        source="Yahoo Finance", country=market_for(ticker).country,
    )
