"""Wires the agents into a LangGraph graph.

        profile
       /   |   \\
 fundamentals news market     <- run at the same time
       \\   |   /
         risk                 <- waits for all three
"""
from datetime import date
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from memograph.research.agents import fundamentals_agent, market_agent, news_agent, profile, risk_agent


def merge(a: dict | None, b: dict | None) -> dict:
    """Parallel agents may write errors/timings at the same time: combine instead of overwrite."""
    return {**(a or {}), **(b or {})}


class ResearchState(TypedDict, total=False):
    ticker: str
    as_of: date | None          # None = today; a past date in backtests (no look-ahead)
    company_name: str
    country: str
    fundamentals_data: dict | None
    ratios: dict
    market_stats: dict
    news_items: list[dict]
    fundamentals: dict          # each agent's filled-in form
    news: dict
    market: dict
    risk: dict
    errors: Annotated[dict, merge]
    timings: Annotated[dict, merge]


def build_graph():
    g = StateGraph(ResearchState)
    g.add_node("profile", profile)
    g.add_node("fundamentals_agent", fundamentals_agent)
    g.add_node("news_agent", news_agent)
    g.add_node("market_agent", market_agent)
    g.add_node("risk_agent", risk_agent)

    g.add_edge(START, "profile")
    for agent in ("fundamentals_agent", "news_agent", "market_agent"):
        g.add_edge("profile", agent)
    g.add_edge(["fundamentals_agent", "news_agent", "market_agent"], "risk_agent")  # join: wait for all three
    g.add_edge("risk_agent", END)
    return g.compile()


async def run_research(ticker: str, as_of: date | None = None) -> dict:
    return await build_graph().ainvoke({"ticker": ticker.upper(), "as_of": as_of, "errors": {}, "timings": {}})
