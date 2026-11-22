"""Phase 1 health check: is everything the project needs running?

Run:  python scripts/check_setup.py
"""
import asyncio

import httpx
import redis.asyncio as redis
from pydantic import BaseModel
from sqlalchemy import text

from memograph.core.config import settings
from memograph.core.db import get_engine
from memograph.core.llm import get_provider


class Ping(BaseModel):
    ok: bool
    message: str


async def check_postgres() -> str:
    async with get_engine().begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        version = (await conn.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))).scalar()
    return f"Postgres OK, pgvector {version}"


async def check_redis() -> str:
    r = redis.from_url(settings.redis_url)
    await r.ping()
    await r.aclose()
    return "Redis OK"


async def check_ollama() -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        tags = (await client.get(f"{settings.ollama_url}/api/tags")).json()
    names = [m["name"] for m in tags.get("models", [])]
    for model in {settings.specialist_model, settings.orchestrator_model}:
        if model not in names:
            raise RuntimeError(f"model '{model}' missing. Run: ollama pull {model}  (you have: {names})")
    reply = await get_provider().generate_structured(
        "Reply with ok=true and a one-word message.", Ping, model=settings.specialist_model
    )
    return f"Ollama OK, {settings.specialist_model} answered: {reply}"


async def main() -> None:
    for name, check in [("Postgres", check_postgres), ("Redis", check_redis), ("Ollama", check_ollama)]:
        try:
            print("PASS", await check())
        except Exception as e:
            print("FAIL", name, "->", e)


if __name__ == "__main__":
    asyncio.run(main())
