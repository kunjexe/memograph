"""Research one company, write its memo, check the citations, save it, and print it.

Run:  PYTHONPATH=src python scripts/run_memo.py DBK.DE
The memo is also written to output/<ticker>-<date>.md
"""
import asyncio
import logging
import sys
import time
from datetime import date
from pathlib import Path

from memograph.data.cache import init_db
from memograph.research.graph import run_research
from memograph.research.memo import to_markdown
from memograph.research.storage import save_memo


async def main(ticker: str) -> None:
    await init_db()
    t0 = time.perf_counter()
    state = await run_research(ticker)
    took = time.perf_counter() - t0

    if not state.get("memo"):
        print("No memo was produced. Errors:", state.get("errors"))
        return
    memo_id = await save_memo(state)
    md = to_markdown(state)
    out = Path("output") / f"{state['ticker']}-{date.today()}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(md)

    print(md)
    if state.get("errors"):
        print("Errors (the run continued without these):", state["errors"])
    print("Time per step:", ", ".join(f"{k} {v}s" for k, v in state.get("timings", {}).items()))
    print(f"Total {took:.0f}s | saved as memo {memo_id} | file {out}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="  ! %(message)s")
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "SAP.DE"))
