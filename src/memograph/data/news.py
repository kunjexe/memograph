"""News articles from NewsAPI, cached for 6 hours."""
import re
from datetime import date, timedelta

import httpx

from memograph.core.config import settings
from memograph.data.cache import cached
from memograph.data.schemas import NewsArticle

NEWSAPI_URL = "https://newsapi.org/v2/everything"
_SUFFIXES = r"\b(inc|incorporated|corp|corporation|co|company|ltd|plc|holdings|group|/de/?)\b\.?"


def company_query(company_name: str, ticker: str) -> str:
    """'Apple Inc.' + 'AAPL' -> '"apple" OR AAPL' (people write 'Apple', not 'Apple Inc.')."""
    clean = re.sub(_SUFFIXES, "", company_name.lower())
    clean = re.sub(r"[^a-z0-9& ]", " ", clean)
    clean = " ".join(clean.split())
    return f'"{clean}" OR {ticker.upper()}'


async def get_news(query: str, end: date | None = None, days: int = 30) -> list[NewsArticle]:
    """Up to 50 recent English articles matching `query`, newest first."""
    if not settings.newsapi_key:
        return []  # June lesson: a missing key means "no news", never a crash
    end = end or date.today()
    start = end - timedelta(days=days)

    async def fetch() -> list[dict]:
        params = {
            "q": query, "from": start.isoformat(), "to": end.isoformat(),
            "language": "en", "sortBy": "publishedAt", "pageSize": 50,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(NEWSAPI_URL, params=params, headers={"X-Api-Key": settings.newsapi_key})
        r.raise_for_status()
        return [
            {
                "title": a["title"], "source": a["source"]["name"], "url": a["url"],
                "published_at": a["publishedAt"], "description": a.get("description"),
            }
            for a in r.json().get("articles", [])
            if a.get("title") and a["title"] != "[Removed]"
        ]

    payload = await cached("news", f"{query}:{start}:{end}", fetch)
    return [NewsArticle(**a) for a in payload]
