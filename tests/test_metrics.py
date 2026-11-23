from datetime import date, timedelta

from memograph.data.schemas import FinancialFact, Fundamentals, PriceBar
from memograph.research.metrics import fundamental_ratios, market_stats


def fact(v):
    return FinancialFact(value=v, unit="EUR", period_end=date(2025, 12, 31), form="x", filed=date(2026, 3, 1))


def test_fundamental_ratios():
    f = Fundamentals(ticker="T", company_name="T", facts={
        "revenue": fact(100), "net_income": fact(20), "stockholders_equity": fact(80),
        "operating_cash_flow": fact(30), "capex": fact(10)})
    r = fundamental_ratios(f)
    assert r["net_margin"] == 0.2 and r["return_on_equity"] == 0.25
    assert r["free_cash_flow"] == 20 and r["fcf_margin"] == 0.2
    assert "debt_to_equity" not in r  # no debt figure -> left out, not guessed


def test_market_stats():
    start = date(2025, 1, 1)
    closes = list(range(50, 250)) + [250, 200]  # steady rise to a peak of 250, then a fall
    prices = [PriceBar(day=start + timedelta(days=i), close=c, volume=1) for i, c in enumerate(closes)]
    s = market_stats(prices)
    assert s["last_close"] == 200 and s["days_of_data"] == 202
    assert s["max_drawdown"] == -0.2           # 250 -> 200
    assert "ma200" in s and "ma50" in s
