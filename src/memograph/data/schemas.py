"""The shapes of the data we fetch. Agents receive these, never raw API JSON."""
from datetime import date, datetime

from pydantic import BaseModel


class PriceBar(BaseModel):
    day: date
    close: float
    volume: int


class NewsArticle(BaseModel):
    title: str
    source: str
    url: str
    published_at: datetime
    description: str | None = None
    language: str = "en"


class FinancialFact(BaseModel):
    value: float
    unit: str          # e.g. "USD"
    period_end: date   # last day of the fiscal year it covers
    form: str          # "10-K" = the yearly report
    filed: date        # when the company published it


class Fundamentals(BaseModel):
    ticker: str
    company_name: str
    facts: dict[str, FinancialFact]  # e.g. "revenue" -> latest yearly value
    source: str = "SEC EDGAR"        # or "Yahoo Finance" outside the US
    country: str = "United States"
    cik: str | None = None           # the SEC's ID number (US companies only)
    source_url: str | None = None    # link to the original report, for citations
