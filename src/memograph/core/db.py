"""Database connection.

Lesson from the June build: an async session must NEVER be shared by agents
running at the same time. So we expose a session *factory*: each agent calls
get_session_factory()() to open its own session.
"""
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from memograph.core.config import settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
