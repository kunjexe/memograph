"""Share prices from Yahoo Finance (yfinance), cached for 1 hour."""
import asyncio
from datetime import date, timedelta

import yfinance as yf

from memograph.data.cache import cached
from memograph.data.schemas import PriceBar


async def get_prices(ticker: str, end: date | None = None, days: int = 365) -> list[PriceBar]:
    """Daily closing prices for the `days` before `end`.

    `end` itself is excluded. Later, the backtest passes a past date here so the
    bot can never see prices from "the future" (no look-ahead bias).
    """
    end = end or date.today()
    start = end - timedelta(days=days)

    def fetch_sync() -> list[dict]:
        df = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat(), auto_adjust=True)
        rows = []
        for idx, row in df.iterrows():
            close, volume = row["Close"], row["Volume"]
            if close != close or volume != volume:  # NaN: Yahoo sometimes sends an incomplete latest day
                continue
            rows.append({"day": idx.date().isoformat(), "close": float(close), "volume": int(volume)})
        return rows

    async def fetch() -> list[dict]:
        rows = await asyncio.to_thread(fetch_sync)  # yfinance isn't async, so run it in a thread
        if not rows:
            raise ValueError(f"No price data for {ticker}")
        return rows

    payload = await cached("prices", f"{ticker.upper()}:{start}:{end}", fetch)
    return [PriceBar(**r) for r in payload]
