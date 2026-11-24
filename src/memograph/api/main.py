"""HTTP API for MemoGraph.

Run:   PYTHONPATH=src uvicorn memograph.api.main:app --reload
Then open http://localhost:8000/docs to try every endpoint in the browser.

A memo takes 1-3 minutes, so POST /research answers at once with a job id, the work
runs in the background, and the job's status is kept in Redis.
"""
import asyncio
import time
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from memograph.core.config import settings
from memograph.data.cache import init_db
from memograph.data.markets import market_for
from memograph.research.graph import stream_research
from memograph.research.memo import to_markdown
from memograph.research.storage import get_memo, list_memos, save_memo

JOB_TTL_S = 24 * 3600          # job status is kept for a day
_running: set[asyncio.Task] = set()  # keep references so background tasks aren't garbage-collected
r = redis.from_url(settings.redis_url, decode_responses=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # A job that was "running" when the server stopped (e.g. --reload after a file change) will never
    # finish: mark it failed instead of leaving it "running" forever.
    async for key in r.scan_iter("job:*"):
        if await r.hget(key, "status") in ("queued", "running"):
            await r.hset(key, mapping={"status": "failed", "error": "server restarted while the job was running"})
    yield
    await r.aclose()


app = FastAPI(title="MemoGraph", description="Multi-agent equity research with cited memos.", lifespan=lifespan)


class ResearchRequest(BaseModel):
    ticker: str  # Yahoo style: AAPL, SAP.DE, DBK.DE, RELIANCE.NS


async def _set(job_id: str, **fields) -> None:
    await r.hset(f"job:{job_id}", mapping={k: str(v) for k, v in fields.items()})
    await r.expire(f"job:{job_id}", JOB_TTL_S)


STEPS = ["profile", "fundamentals", "news", "market", "risk", "memo_writer", "citation_check"]


async def _run(job_id: str, ticker: str) -> None:
    await _set(job_id, status="running", started_at=time.time(), steps_done="", steps_total=len(STEPS))
    try:
        state = {}
        async for state in stream_research(ticker):
            done = [s for s in STEPS if s in (state.get("timings") or {})]
            await _set(job_id, steps_done=", ".join(done))
        if not state.get("memo"):
            raise RuntimeError(f"no memo produced; errors: {state.get('errors')}")
        await _set(job_id, status="done", memo_id=await save_memo(state))
    except Exception as e:
        await _set(job_id, status="failed", error=f"{type(e).__name__}: {e}")


@app.post("/research", status_code=202)
async def start_research(req: ResearchRequest) -> dict:
    ticker = req.ticker.strip().upper()
    try:
        market_for(ticker)
    except ValueError as e:
        raise HTTPException(400, str(e))
    job_id = uuid.uuid4().hex
    await _set(job_id, status="queued", ticker=ticker)
    task = asyncio.create_task(_run(job_id, ticker))
    _running.add(task)
    task.add_done_callback(_running.discard)
    return {"job_id": job_id, "status_url": f"/jobs/{job_id}"}


@app.get("/jobs/{job_id}")
async def job_status(job_id: str) -> dict:
    data = await r.hgetall(f"job:{job_id}")
    if not data:
        raise HTTPException(404, "unknown or expired job")
    if data.get("started_at"):
        data["elapsed_seconds"] = round(time.time() - float(data.pop("started_at")))
    if data.get("memo_id"):
        data["memo_url"] = f"/memos/{data['memo_id']}/markdown"
    return data


@app.get("/memos")
async def memos(ticker: str | None = None) -> list[dict]:
    return await list_memos(ticker)


@app.get("/memos/{memo_id}")
async def memo_json(memo_id: str) -> dict:
    state = await get_memo(memo_id)
    if not state:
        raise HTTPException(404, "memo not found")
    return state


@app.get("/memos/{memo_id}/markdown", response_class=PlainTextResponse)
async def memo_markdown(memo_id: str) -> str:
    state = await get_memo(memo_id)
    if not state:
        raise HTTPException(404, "memo not found")
    return to_markdown(state)


@app.get("/health")
async def health() -> dict:
    await r.ping()
    return {"status": "ok"}
