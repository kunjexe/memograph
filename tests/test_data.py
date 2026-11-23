"""Fast tests with no network and no database."""
from datetime import date, datetime, timedelta, timezone

from memograph.core.config import settings
from memograph.data.cache import is_fresh
from memograph.data.edgar import latest_annual
from memograph.data.news import company_query, get_news


def test_is_fresh():
    now = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
    assert is_fresh(now - timedelta(minutes=30), timedelta(hours=1), now)
    assert not is_fresh(now - timedelta(hours=2), timedelta(hours=1), now)


FAKE_FACTS = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
    # FY2024, as reported in the 2024 10-K
    {"start": "2023-10-01", "end": "2024-09-30", "val": 100, "form": "10-K", "fp": "FY", "filed": "2024-11-01"},
    # FY2025 full year
    {"start": "2024-10-01", "end": "2025-09-30", "val": 120, "form": "10-K", "fp": "FY", "filed": "2025-11-01"},
    # a single quarter inside the 2025 10-K: must be ignored
    {"start": "2025-07-01", "end": "2025-09-30", "val": 35, "form": "10-K", "fp": "FY", "filed": "2025-11-01"},
    # a quarterly report: must be ignored
    {"start": "2025-10-01", "end": "2025-12-31", "val": 40, "form": "10-Q", "fp": "Q1", "filed": "2026-02-01"},
]}}}}}


def test_latest_annual_picks_newest_full_year():
    fact = latest_annual(FAKE_FACTS, ["Revenues"])
    assert fact.value == 120 and fact.period_end == date(2025, 9, 30)


def test_latest_annual_no_look_ahead():
    # Deciding on 2025-06-01, the FY2025 report didn't exist yet.
    fact = latest_annual(FAKE_FACTS, ["Revenues"], before=date(2025, 6, 1))
    assert fact.value == 100


def test_company_query():
    assert company_query("Apple Inc.", "aapl") == '"apple" OR AAPL'
    assert company_query("MICROSOFT CORP", "MSFT") == '"microsoft" OR MSFT'


async def test_news_without_key_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "newsapi_key", "")
    assert await get_news("apple") == []


async def test_news_relevance_interleave_and_dedupe(monkeypatch):
    from memograph.data import news as news_mod
    def art(title, url, lang):
        return {"title": title, "source": "s", "url": url, "published_at": "2026-11-20T10:00:00Z",
                "description": None, "language": lang}
    fake = {
        "de": [art("Bank Skandal", "u1", "de"), art("Zweite", "u2", "de")],
        "en": [art("Bank scandal deepens", "u3", "en"), art("bank SKANDAL", "u4", "en")],
    }
    async def fetch(query, lang, start, end):
        return fake[lang]
    monkeypatch.setattr(settings, "newsapi_key", "x" * 32)
    monkeypatch.setattr(news_mod, "_fetch_language", fetch)
    titles = [a.title for a in await get_news("q", languages=("de", "en"))]
    assert titles == ["Bank Skandal", "Bank scandal deepens", "Zweite"]  # interleaved, duplicate headline dropped
