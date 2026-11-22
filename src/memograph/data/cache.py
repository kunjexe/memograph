"""A Postgres cache in front of every outside API.

Why: free APIs have rate limits, repeated runs should be fast, and saved data
makes tests and demos repeatable. Each source has its own "freshness" time (TTL).
If an API call fails but we have an older copy, we use the old copy rather than crash.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from memograph.core.db import get_engine, get_session_factory


class Base(DeclarativeBase):
    pass


class CacheEntry(Base):
    __tablename__ = "cache_entries"
    source: Mapped[str] = mapped_column(String(32), primary_key=True)   # "edgar", "news", "prices"
    key: Mapped[str] = mapped_column(String(256), primary_key=True)     # e.g. "AAPL:2025-11-22:2026-11-22"
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[Any] = mapped_column(JSONB)


TTL = {
    "edgar": timedelta(days=30),   # filings change a few times a year
    "news": timedelta(hours=6),
    "prices": timedelta(hours=1),
}


def is_fresh(fetched_at: datetime, ttl: timedelta, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return now - fetched_at < ttl


async def init_db() -> None:
    """Create the tables if they don't exist yet."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def cached(source: str, key: str, fetch: Callable[[], Awaitable[Any]]) -> Any:
    """Return the stored copy if fresh; otherwise call fetch(), store the result, return it."""
    async with get_session_factory()() as session:
        entry = await session.get(CacheEntry, (source, key))
        if entry and is_fresh(entry.fetched_at, TTL[source]):
            return entry.payload
        try:
            payload = await fetch()
        except Exception:
            if entry:  # API down: an old copy beats no data
                return entry.payload
            raise
        stmt = insert(CacheEntry).values(
            source=source, key=key, fetched_at=datetime.now(timezone.utc), payload=payload
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["source", "key"],
            set_={"fetched_at": stmt.excluded.fetched_at, "payload": stmt.excluded.payload},
        )
        await session.execute(stmt)
        await session.commit()
        return payload
