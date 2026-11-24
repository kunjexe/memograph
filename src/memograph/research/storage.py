"""Saved memos in Postgres: one row per memo, with everything needed to show or audit it."""
import json
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Date, DateTime, Float, Integer, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from memograph.core.db import get_session_factory
from memograph.data.cache import Base

KEEP = [
    "ticker", "as_of", "company_name", "country", "sector", "financial_company", "fundamentals_data",
    "ratios", "market_stats", "news_items", "fundamentals", "news", "market", "risk",
    "memo", "sources", "citation_report", "errors", "timings",
]


class MemoRecord(Base):
    __tablename__ = "memos"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    company_name: Mapped[str] = mapped_column(String(256))
    as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recommendation: Mapped[str] = mapped_column(String(8))
    confidence: Mapped[int] = mapped_column(Integer)
    faithfulness: Mapped[float] = mapped_column(Float)
    state: Mapped[Any] = mapped_column(JSONB)  # analyses, memo, sources, citation report: the full audit trail


async def save_memo(state: dict) -> str:
    memo = state["memo"]
    record = MemoRecord(
        id=str(uuid.uuid4()), ticker=state["ticker"], company_name=state.get("company_name") or state["ticker"],
        as_of=state.get("as_of"), created_at=datetime.now(timezone.utc),
        recommendation=memo["recommendation"], confidence=memo["confidence"],
        faithfulness=state.get("citation_report", {}).get("faithfulness", 0.0),
        state=json.loads(json.dumps({k: state.get(k) for k in KEEP}, default=str)),
    )
    async with get_session_factory()() as session:
        session.add(record)
        await session.commit()
    return record.id


async def get_memo(memo_id: str) -> dict | None:
    async with get_session_factory()() as session:
        rec = await session.get(MemoRecord, memo_id)
        return rec.state if rec else None


async def list_memos(ticker: str | None = None, limit: int = 20) -> list[dict]:
    q = select(MemoRecord).order_by(MemoRecord.created_at.desc()).limit(limit)
    if ticker:
        q = q.where(MemoRecord.ticker == ticker.upper())
    async with get_session_factory()() as session:
        rows = (await session.execute(q)).scalars().all()
    return [
        {"id": r.id, "ticker": r.ticker, "company": r.company_name, "created_at": r.created_at.isoformat(),
         "recommendation": r.recommendation, "confidence": r.confidence, "faithfulness": r.faithfulness}
        for r in rows
    ]
