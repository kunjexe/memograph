"""News articles from NewsAPI, cached for 6 hours, in one or more languages."""
import re
from datetime import date, timedelta

import httpx

from memograph.core.config import settings
from memograph.data.cache import cached
from memograph.data.markets import base_symbol
from memograph.data.schemas import NewsArticle

NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Legal-form words that people don't use when writing about a company.
_LEGAL_WORDS = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc",
    "holdings", "holding", "group", "ag", "se", "sa", "nv", "spa", "gmbh", "kgaa", "the",
}


def company_query(company_name: str, ticker: str) -> str:
    """'SAP SE' + 'SAP.DE' -> '"sap" OR SAP';  'Toyota Motor Corporation' + '7203.T' -> '"toyota motor"'."""
    name = re.sub(r"/[a-z]{2}/?", " ", company_name.lower())        # SEC's "/DE/" state marks
    name = re.sub(r"\b([a-z])\.(?=[a-z]\.)", r"\1", name)           # "s.p.a." / "n.v." -> "spa" / "nv"
    name = re.sub(r"\b([a-z])\.", r"\1", name)
    tokens = [t for t in re.sub(r"[^a-z0-9& ]", " ", name).split() if t not in _LEGAL_WORDS]
    query = f'"{" ".join(tokens)}"'
    symbol = base_symbol(ticker).upper()
    if symbol.isalpha():  # "7203" is a useless search word; "SAP" is a good one
        query += f" OR {symbol}"
    return query


async def _fetch_language(query: str, lang: str, start: date, end: date) -> list[dict]:
    async def fetch() -> list[dict]:
        params = {
            "q": query, "from": start.isoformat(), "to": end.isoformat(),
            "language": lang, "sortBy": "publishedAt", "pageSize": 50,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(NEWSAPI_URL, params=params, headers={"X-Api-Key": settings.newsapi_key})
        r.raise_for_status()
        return [
            {
                "title": a["title"], "source": a["source"]["name"], "url": a["url"],
                "published_at": a["publishedAt"], "description": a.get("description"), "language": lang,
            }
            for a in r.json().get("articles", [])
            if a.get("title") and a["title"] != "[Removed]"
        ]

    return await cached("news", f"{lang}:{query}:{start}:{end}", fetch)


async def get_news(
    query: str, end: date | None = None, days: int = 30, languages: tuple[str, ...] = ("en",)
) -> list[NewsArticle]:
    """Recent articles matching `query` in each language, merged, newest first."""
    if not settings.newsapi_key:
        return []  # June lesson: a missing key means "no news", never a crash
    end = end or date.today()
    start = end - timedelta(days=days)
    seen, articles = set(), []
    for lang in languages:
        for a in await _fetch_language(query, lang, start, end):
            if a["url"] not in seen:
                seen.add(a["url"])
                articles.append(NewsArticle(**a))
    return sorted(articles, key=lambda a: a.published_at, reverse=True)
