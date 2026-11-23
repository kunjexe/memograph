"""ESEF parsing with a small fake filing: no network needed."""
from datetime import date

from memograph.data.esef import extract_fact, parse_period, pick_filing
from memograph.data.markets import market_for


def test_parse_period():
    assert parse_period("2025-01-01T00:00:00/2026-01-01T00:00:00") == (date(2025, 1, 1), date(2025, 12, 31))
    assert parse_period("2026-01-01T00:00:00") == (None, date(2025, 12, 31))


FAKE_XBRL = {"facts": {
    # this year's group revenue
    "f1": {"value": "34000000000", "dimensions": {"concept": "ifrs-full:Revenue", "entity": "lei:X",
           "period": "2025-01-01T00:00:00/2026-01-01T00:00:00", "unit": "iso4217:EUR"}}},
}
FAKE_XBRL["facts"].update({
    # last year's comparison figure: ignore
    "f2": {"value": "31000000000", "dimensions": {"concept": "ifrs-full:Revenue", "entity": "lei:X",
           "period": "2024-01-01T00:00:00/2025-01-01T00:00:00", "unit": "iso4217:EUR"}},
    # revenue of one segment: ignore
    "f3": {"value": "9000000000", "dimensions": {"concept": "ifrs-full:Revenue", "entity": "lei:X",
           "period": "2025-01-01T00:00:00/2026-01-01T00:00:00", "unit": "iso4217:EUR",
           "ifrs-full:SegmentsAxis": "x:CloudMember"}},
    # Q4 only: ignore
    "f4": {"value": "9500000000", "dimensions": {"concept": "ifrs-full:Revenue", "entity": "lei:X",
           "period": "2025-10-01T00:00:00/2026-01-01T00:00:00", "unit": "iso4217:EUR"}},
    # cash at year end (an instant)
    "f5": {"value": "8000000000", "dimensions": {"concept": "ifrs-full:CashAndCashEquivalents", "entity": "lei:X",
           "period": "2026-01-01T00:00:00", "unit": "iso4217:EUR"}},
})


def test_extract_group_total_for_the_year():
    assert extract_fact(FAKE_XBRL, ["ifrs-full:Revenue"], date(2025, 12, 31)) == (34e9, "EUR")


def test_extract_instant_and_missing():
    assert extract_fact(FAKE_XBRL, ["ifrs-full:CashAndCashEquivalents"], date(2025, 12, 31)) == (8e9, "EUR")
    assert extract_fact(FAKE_XBRL, ["ifrs-full:Assets"], date(2025, 12, 31)) is None


FILINGS = [
    {"period_end": "2024-12-31", "published": "2025-03-10", "json_url": "/a", "errors": 0},
    {"period_end": "2025-12-31", "published": "2026-03-12", "json_url": "/b-de", "errors": 3},
    {"period_end": "2025-12-31", "published": "2026-03-12", "json_url": "/b-en", "errors": 0},
]


def test_pick_newest_cleanest_filing():
    assert pick_filing(FILINGS)["json_url"] == "/b-en"


def test_pick_filing_no_look_ahead():
    # On 1 Mar 2026 the 2025 report wasn't published yet.
    assert pick_filing(FILINGS, before=date(2026, 3, 1))["json_url"] == "/a"


def test_source_order_per_market():
    assert market_for("SAP.DE").fundamentals_sources == ("yahoo",)  # no German filings on filings.xbrl.org
    assert market_for("ASML.AS").fundamentals_sources == ("esef", "yahoo")
    assert market_for("AAPL").fundamentals_sources == ("edgar",)
    assert market_for("7203.T").fundamentals_sources == ("yahoo",)
