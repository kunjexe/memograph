"""Fetch everything for one company, twice. The second run should come from the cache.

Run:  PYTHONPATH=src python scripts/try_data.py AAPL
      PYTHONPATH=src python scripts/try_data.py SAP.DE SIE.DE ALV.DE RELIANCE.NS
"""
import asyncio
import logging
import sys
import time

from memograph.data.cache import init_db
from memograph.data.fundamentals import get_fundamentals
from memograph.data.market import get_prices
from memograph.data.markets import market_for
from memograph.data.news import company_query, get_news


async def show(ticker: str) -> None:
    market = market_for(ticker)
    for run in (1, 2):
        t0 = time.perf_counter()
        f = await get_fundamentals(ticker)
        prices = await get_prices(ticker)
        news = await get_news(company_query(f.company_name, ticker), languages=market.news_languages)
        took = time.perf_counter() - t0

        print(f"\n=== {ticker} run {run} ({'fresh from APIs' if run == 1 else 'from cache'}): {took:.2f}s ===")
        print(f"{f.company_name} | {market.country}, {market.exchange} | financials from {f.source}")
        if f.source_url:
            print(f"  report: {f.source_url}")
        for name in ("revenue", "net_income", "cash"):
            if name in f.facts:
                fact = f.facts[name]
                print(f"  {name}: {fact.value / 1e9:,.1f} bn {fact.unit} (year ending {fact.period_end})")
        print(f"Prices: {len(prices)} days, last close {prices[-1].close:.2f} on {prices[-1].day}")
        print(f"News ({', '.join(market.news_languages)}): {len(news)} articles" + ("" if news else " (no NewsAPI key in .env?)"))
        for a in news[:3]:
            print(f"  - {a.published_at:%Y-%m-%d} [{a.language}] {a.source}: {a.title}")


async def main(tickers: list[str]) -> None:
    await init_db()
    for t in tickers:
        try:
            await show(t)
        except Exception as e:
            print(f"\n=== {t}: FAILED -> {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="  ! %(message)s")
    asyncio.run(main(sys.argv[1:] or ["AAPL"]))
