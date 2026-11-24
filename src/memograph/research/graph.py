"""Wires the agents into a LangGraph graph.

        profile
       /   |   \\
 fundamentals news market     <- run at the same time
       \\   |   /
         risk                 <- waits for all three
          |
      memo_writer             <- AI writes a cited memo
          |
     citation_check           <- plain code drops unsupported claims
"""
from datetime import date
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from memograph.research.agents import (
    citation_check, fundamentals_agent, market_agent, memo_writer, news_agent, profile, risk_agent,
)


def merge(a: dict | None, b: dict | None) -> dict:
    """Parallel agents may write errors/timings at the same time: combine instead of overwrite."""
    return {**(a or {}), **(b or {})}


class ResearchState(TypedDict, total=False):
    ticker: str
    as_of: date | None          # None = today; a past date in backtests (no look-ahead)
    company_name: str
    country: str
    sector: dict                # {'sector': ..., 'industry': ...} from Yahoo
    financial_company: bool     # bank/insurer: judged differently
    fundamentals_data: dict | None
    ratios: dict
    market_stats: dict
    news_items: list[dict]
    fundamentals: dict          # each agent's filled-in form
    news: dict
    market: dict
    risk: dict
    memo_draft: dict            # the AI's memo before checking
    sources: dict               # id -> {label, url}: what the memo may cite
    memo: dict                  # the memo after the citation check
    citation_report: dict       # kept / dropped claims and why
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
    g.add_node("memo_writer", memo_writer)
    g.add_node("citation_check", citation_check)
    g.add_edge("risk_agent", "memo_writer")
    g.add_edge("memo_writer", "citation_check")
    g.add_edge("citation_check", END)
    return g.compile()


async def run_research(ticker: str, as_of: date | None = None) -> dict:
    return await build_graph().ainvoke({"ticker": ticker.upper(), "as_of": as_of, "errors": {}, "timings": {}})


async def stream_research(ticker: str, as_of: date | None = None):
    """Like run_research, but yields the state after every step, so callers can show progress.
    The steps finished so far are the keys of state['timings']."""
    inputs = {"ticker": ticker.upper(), "as_of": as_of, "errors": {}, "timings": {}}
    async for state in build_graph().astream(inputs, stream_mode="values"):
        yield state
