"""Diagnose why filings.xbrl.org returns nothing. Prints what the API really sends back.

Run:  PYTHONPATH=src python scripts/probe_esef.py
"""
import asyncio
import json

import httpx
from sqlalchemy import text

from memograph.core.db import get_engine

API = "https://filings.xbrl.org/api/filings"
LEI = "529900D6BF99LW9R2E68"  # SAP SE


async def show(label: str, params: dict) -> None:
    async with httpx.AsyncClient(timeout=60, headers={"User-Agent": "MemoGraph probe"}) as c:
        r = await c.get(API, params=params)
    print(f"\n--- {label} ---\nURL: {r.url}\nHTTP {r.status_code}")
    try:
        data = r.json()
    except Exception:
        print(r.text[:500]); return
    items = data.get("data", [])
    print(f"meta: {data.get('meta')} | items on this page: {len(items)}")
    if items:
        print("first item attributes:", json.dumps(items[0].get("attributes", {}), indent=1)[:1200])
        print("first item relationships:", json.dumps(items[0].get("relationships", {}))[:300])
    ents = [e.get("attributes", {}) for e in data.get("included", [])][:5]
    if ents:
        print("included entities (first 5):", json.dumps(ents)[:600])
    if "errors" in data:
        print("errors:", data["errors"])


async def main() -> None:
    # Remove any empty filing lists cached by the earlier run
    async with get_engine().begin() as conn:
        n = (await conn.execute(text("DELETE FROM cache_entries WHERE key LIKE 'esef:filings:%'"))).rowcount
    print(f"cleared {n} cached ESEF filing lists")

    await show("1. SAP by LEI (what our code does)", {
        "filter": json.dumps([{"name": "entity.identifier", "op": "eq", "val": LEI}]),
        "include": "entity", "page[size]": 5})
    await show("2. Any German filings at all?", {"filter[country]": "DE", "include": "entity", "page[size]": 3})
    await show("3. SAP by name", {
        "filter": json.dumps([{"name": "entity.name", "op": "ilike", "val": "%sap%"}]),
        "include": "entity", "page[size]": 5})
    await show("4. Newest filings of any country (to see field names)", {"sort": "-processed", "page[size]": 1})


asyncio.run(main())
