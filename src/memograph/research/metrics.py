"""All the maths, in plain Python. The LLM never calculates; it only interprets these numbers.

Why: small local models make arithmetic mistakes, and code is testable.
Ratios are fractions: 0.25 means 25%.
"""
import math
from statistics import mean, stdev

from memograph.data.schemas import Fundamentals, PriceBar

TRADING_DAYS = 252  # trading days in a year


def fundamental_ratios(f: Fundamentals) -> dict[str, float]:
    v = {k: fact.value for k, fact in f.facts.items()}

    def div(a: str, b: str) -> float | None:
        if a in v and b in v and v[b]:
            return round(v[a] / v[b], 4)
        return None

    r = {
        "net_margin": div("net_income", "revenue"),                 # profit per euro/dollar of sales
        "return_on_equity": div("net_income", "stockholders_equity"),
        "debt_to_equity": div("long_term_debt", "stockholders_equity"),
        "liabilities_to_assets": div("total_liabilities", "total_assets"),
    }
    if "operating_cash_flow" in v and "capex" in v:
        fcf = v["operating_cash_flow"] - v["capex"]                 # free cash flow: cash left after investing
        r["free_cash_flow"] = round(fcf, 0)
        if v.get("revenue"):
            r["fcf_margin"] = round(fcf / v["revenue"], 4)
    return {k: x for k, x in r.items() if x is not None}


def market_stats(prices: list[PriceBar]) -> dict[str, float]:
    closes = [p.close for p in prices]
    if len(closes) < 2:
        raise ValueError("not enough price history")
    last = closes[-1]

    def ret(days: int) -> float | None:
        return round(last / closes[-1 - days] - 1, 4) if len(closes) > days else None

    daily = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    peak, max_dd = closes[0], 0.0
    for c in closes:  # biggest fall from a high point during the period
        peak = max(peak, c)
        max_dd = min(max_dd, c / peak - 1)

    s = {
        "last_close": round(last, 2),
        "return_1m": ret(21),
        "return_3m": ret(63),
        "return_6m": ret(126),
        "return_period": round(last / closes[0] - 1, 4),
        "volatility_annual": round(stdev(daily) * math.sqrt(TRADING_DAYS), 4) if len(daily) > 1 else None,
        "max_drawdown": round(max_dd, 4),
        "days_of_data": len(closes),
    }
    for n in (50, 200):  # moving averages: the average price of the last n days
        if len(closes) >= n:
            ma = mean(closes[-n:])
            s[f"ma{n}"] = round(ma, 2)
            s[f"price_vs_ma{n}"] = round(last / ma - 1, 4)
    return {k: x for k, x in s.items() if x is not None}
