"""One entry point for company financials, whatever the country.

Each market lists its sources in order (see markets.py). We try them one by one
and return the first that gives usable numbers, logging why any source was skipped.
Agents only ever call get_fundamentals().
"""
import logging
from datetime import date

from memograph.data import edgar, esef, yahoo_fundamentals
from memograph.data.markets import market_for
from memograph.data.schemas import Fundamentals

log = logging.getLogger(__name__)

# To add a source: write a module with get_fundamentals(ticker, before) and register it here.
SOURCES = {
    "edgar": edgar.get_fundamentals,               # US: SEC filings
    "esef": esef.get_fundamentals,                 # EU/UK: ESEF filings via filings.xbrl.org
    "yahoo": yahoo_fundamentals.get_fundamentals,  # anywhere: Yahoo Finance
}
MIN_FACTS = 3  # fewer usable numbers than this = treat the source as failed


async def get_fundamentals(ticker: str, before: date | None = None) -> Fundamentals:
    errors = []
    for name in market_for(ticker).fundamentals_sources:
        try:
            result = await SOURCES[name](ticker, before)
            if len(result.facts) >= MIN_FACTS:
                return result
            errors.append(f"{name}: only {len(result.facts)} usable numbers")
        except Exception as e:
            errors.append(f"{name}: {e}")
        log.warning("%s: source '%s' skipped -> %s", ticker, name, errors[-1])
    raise ValueError(f"No financials for {ticker}: " + " | ".join(errors))
