from datetime import date

import pytest

from memograph.data.markets import US, base_symbol, market_for
from memograph.data.news import company_query
from memograph.data.yahoo_fundamentals import latest_from_statements


def test_market_for():
    assert market_for("AAPL") is US
    assert market_for("SAP.DE").country == "Germany"
    assert market_for("reliance.ns").country == "India"
    assert "de" in market_for("SAP.DE").news_languages
    with pytest.raises(ValueError):
        market_for("XYZ.QQ")


def test_base_symbol():
    assert base_symbol("SAP.DE") == "SAP"
    assert base_symbol("AAPL") == "AAPL"


def test_company_query_international():
    assert company_query("SAP SE", "SAP.DE") == '"sap" OR SAP'
    assert company_query("Reliance Industries Limited", "RELIANCE.NS") == '"reliance industries" OR RELIANCE'
    assert company_query("Toyota Motor Corporation", "7203.T") == '"toyota motor"'
    assert company_query("Ferrari N.V.", "RACE.MI") == '"ferrari" OR RACE'


PERIODS = {
    "2024-12-31": {"Total Revenue": 30.0e9},
    "2025-12-31": {"Total Revenue": 34.0e9, "Operating Revenue": 33.0e9},
    "2023-12-31": {"Total Revenue": float("nan")},
}


def test_yahoo_latest_year():
    fact = latest_from_statements(PERIODS, ["Total Revenue"], "EUR")
    assert fact.value == 34.0e9 and fact.unit == "EUR" and fact.period_end == date(2025, 12, 31)


def test_yahoo_no_look_ahead():
    # FY2025 assumed public ~31 Mar 2026; deciding on 1 Feb 2026 we only know FY2024.
    fact = latest_from_statements(PERIODS, ["Total Revenue"], "EUR", before=date(2026, 2, 1))
    assert fact.period_end == date(2024, 12, 31)
