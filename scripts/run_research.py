"""Run the four research agents on one company and print what each one concluded.

Run:  PYTHONPATH=src python scripts/run_research.py SAP.DE
"""
import asyncio
import logging
import sys
import time

from memograph.data.cache import init_db
from memograph.research.graph import run_research


def pct(x) -> str:
    return f"{x * 100:+.1f}%" if isinstance(x, (int, float)) else "n/a"


async def main(ticker: str) -> None:
    await init_db()
    t0 = time.perf_counter()
    s = await run_research(ticker)
    total = time.perf_counter() - t0

    print(f"\n#### {s.get('company_name')} ({s['ticker']}), {s.get('country')} ####")

    if f := s.get("fundamentals"):
        r = s.get("ratios", {})
        print(f"\n[Fundamentals] health: {f['financial_health'].upper()}   "
              f"(net margin {pct(r.get('net_margin'))}, ROE {pct(r.get('return_on_equity'))})")
        print(" ", f["summary"])
        for x in f["strengths"]:
            print("   +", x)
        for x in f["weaknesses"]:
            print("   -", x)

    if n := s.get("news"):
        print(f"\n[News] sentiment: {n['sentiment'].upper()}   ({len(s.get('news_items', []))} articles read)")
        print(" ", n["summary"])
        items = {it["id"]: it for it in s.get("news_items", [])}
        for c in n["catalysts"]:
            src = items.get(c["article_id"], {})
            print(f"   * [{c['impact']}] {c['event']}  ({src.get('source')}, {src.get('date')})")

    if m := s.get("market"):
        st = s.get("market_stats", {})
        print(f"\n[Market] trend: {m['trend'].upper()}   (1y {pct(st.get('return_period'))}, "
              f"volatility {pct(st.get('volatility_annual'))}, max drawdown {pct(st.get('max_drawdown'))})")
        print(" ", m["summary"])
        for x in m["observations"]:
            print("   -", x)

    if r := s.get("risk"):
        print(f"\n[Risk] overall: {r['overall_risk'].upper()}")
        print(" ", r["summary"])
        for x in r["risks"]:
            print(f"   ! [{x['severity']}, {x['category']}] {x['description']}")

    if s.get("errors"):
        print("\nErrors (the run continued without these):")
        for k, v in s["errors"].items():
            print(f"   {k}: {v}")
    timings = ", ".join(f"{k} {v}s" for k, v in s.get("timings", {}).items())
    print(f"\nTime per step: {timings}\nTotal: {total:.1f}s")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="  ! %(message)s")
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "SAP.DE"))
