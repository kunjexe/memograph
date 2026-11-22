"""Fetch everything for one company, twice. The second run should come from the cache.

Run:  PYTHONPATH=src python scripts/try_data.py AAPL
"""
import asyncio
import sys
import time

from memograph.data.cache import init_db
from memograph.data.edgar import get_fundamentals
from memograph.data.market import get_prices
from memograph.data.news import company_query, get_news


async def main(ticker: str) -> None:
    await init_db()
    for run in (1, 2):
        t0 = time.perf_counter()
        f = await get_fundamentals(ticker)
        prices = await get_prices(ticker)
        news = await get_news(company_query(f.company_name, ticker))
        took = time.perf_counter() - t0

        print(f"\n=== Run {run} ({'fresh from APIs' if run == 1 else 'from cache'}): {took:.2f}s ===")
        print(f"{f.company_name} (CIK {f.cik}), {len(f.facts)} financial facts")
        for name in ("revenue", "net_income", "cash"):
            if name in f.facts:
                fact = f.facts[name]
                print(f"  {name}: {fact.value / 1e9:,.1f} bn {fact.unit} (year ending {fact.period_end})")
        print(f"Prices: {len(prices)} days, last close {prices[-1].close:.2f} on {prices[-1].day}")
        print(f"News: {len(news)} articles" + ("" if news else " (no NewsAPI key in .env?)"))
        for a in news[:3]:
            print(f"  - {a.published_at:%Y-%m-%d} {a.source}: {a.title}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "AAPL"))
