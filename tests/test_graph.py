"""Runs the whole research graph with fake data and a fake LLM: tests the wiring,
the parallel join, and that one failing agent doesn't stop the others."""
from datetime import date, timedelta

import pytest

from memograph.data.schemas import FinancialFact, Fundamentals, PriceBar
from memograph.research import agents
from memograph.research.graph import run_research

CANNED = {
    "FundamentalsAnalysis": {"financial_health": "strong", "summary": "s", "strengths": ["a"], "weaknesses": ["b"]},
    "NewsAnalysis": {"sentiment": "positive", "summary": "s",
                     "catalysts": [{"article_id": 0, "event": "e", "impact": "positive"},
                                   {"article_id": 99, "event": "invented", "impact": "negative"}]},
    "MarketAnalysis": {"trend": "uptrend", "summary": "s", "observations": ["o"]},
    "RiskAnalysis": {"overall_risk": "medium", "summary": "s",
                     "risks": [{"category": "company", "description": "d", "severity": "low"}]},
    "Memo": {
        "thesis": [{"text": "Test AG is profitable.", "sources": ["F:revenue"]}],
        "fundamentals": [{"text": "Revenue was 100 EUR.", "sources": ["F:revenue"]},
                         {"text": "Revenue was 999 EUR.", "sources": ["F:revenue"]}],
        "recent_developments": [{"text": "Test AG won a contract.", "sources": ["N0"]}],
        "technicals": [{"text": "Invented statistic.", "sources": ["M:made_up"]}],
        "risks": [{"text": "There are risks.", "sources": []}],
        "recommendation": "hold", "confidence": 60,
        "recommendation_reason": [{"text": "Revenue is solid.", "sources": ["F:revenue"]}],
    },
}


class FakeLLM:
    def __init__(self):
        self.prompts = {}

    async def generate_structured(self, prompt, schema, **kw):
        self.prompts[schema.__name__] = prompt
        return schema.model_validate(CANNED[schema.__name__])


class FakeArticle:
    published_at = date(2026, 11, 20)
    source, title, description, url = "Reuters", "Test AG wins contract", "desc", "http://x"


@pytest.fixture
def fake(monkeypatch):
    llm = FakeLLM()
    f = FinancialFact(value=100.0, unit="EUR", period_end=date(2025, 12, 31), form="x", filed=date(2026, 3, 1))

    async def fundamentals(ticker, before=None):
        return Fundamentals(ticker=ticker, company_name="Test AG", facts={"revenue": f, "net_income": f, "operating_cash_flow": f})

    async def prices(ticker, end=None):
        return [PriceBar(day=date(2025, 1, 1) + timedelta(days=i), close=100 + i, volume=1) for i in range(250)]

    async def news(query, end=None, languages=("en",)):
        return [FakeArticle()]

    monkeypatch.setattr(agents, "get_fundamentals", fundamentals)
    monkeypatch.setattr(agents, "get_prices", prices)
    monkeypatch.setattr(agents, "get_news", news)
    async def sector(ticker):
        return {"sector": "Technology", "industry": "Software"}

    monkeypatch.setattr(agents, "get_sector", sector)
    monkeypatch.setattr(agents, "get_provider", lambda: llm)
    return llm


async def test_full_run(fake):
    s = await run_research("test")
    assert s["company_name"] == "Test AG"
    assert s["fundamentals"]["financial_health"] == "strong"
    assert s["market"]["trend"] == "uptrend" and s["market_stats"]["days_of_data"] == 250
    assert s["risk"]["overall_risk"] == "medium"
    assert [c["article_id"] for c in s["news"]["catalysts"]] == [0]   # invented article 99 dropped
    assert s["errors"] == {}
    assert set(s["timings"]) == {"profile", "fundamentals", "news", "market", "risk", "memo_writer", "citation_check"}
    rep = s["citation_report"]
    assert rep["total"] == 7 and rep["kept"] == 4          # 999, M:made_up and the uncited risk dropped
    assert s["memo"]["recommendation"] == "hold" and s["memo"]["confidence"] == 60
    assert "[F:revenue]" in fake.prompts["Memo"] and "[N0]" in fake.prompts["Memo"]


async def test_one_agent_fails_rest_continue(fake, monkeypatch):
    async def broken(ticker, end=None):
        raise ConnectionError("Yahoo down")
    monkeypatch.setattr(agents, "get_prices", broken)
    s = await run_research("test")
    assert "Yahoo down" in s["errors"]["market"]
    assert "market" not in s and s["risk"]["overall_risk"] == "medium"
    assert "MISSING: market" in fake.prompts["RiskAnalysis"]   # risk agent is told what's missing


async def test_no_news_skips_llm(fake, monkeypatch):
    async def none(query, end=None, languages=("en",)):
        return []
    monkeypatch.setattr(agents, "get_news", none)
    s = await run_research("test")
    assert s["news"]["sentiment"] == "neutral" and "NewsAnalysis" not in fake.prompts


async def test_bank_gets_bank_guidance(fake, monkeypatch):
    async def bank(ticker):
        return {"sector": "Financial Services", "industry": "Banks - Regional"}
    monkeypatch.setattr(agents, "get_sector", bank)
    s = await run_research("test")
    assert s["financial_company"] is True
    assert "bank, insurer" in fake.prompts["FundamentalsAnalysis"]
    assert "bank, insurer" in fake.prompts["RiskAnalysis"]
    assert "bank, insurer" in fake.prompts["Memo"]   # the writer needs the bank context too
    assert "operating_cash_flow" not in fake.prompts["FundamentalsAnalysis"]


async def test_data_risk_sentence_only_without_news(fake):
    await run_research("test")   # fake news has 1 article
    assert "No news articles were available" not in fake.prompts["RiskAnalysis"]
