"""The citation checker: plain code, so it can be tested exactly."""
from memograph.research.memo import Claim, Memo, check_claim, check_memo, to_markdown
from memograph.research.sources import build_sources

STATE = {
    "ticker": "TEST.DE", "company_name": "Test AG",
    "fundamentals_data": {"source": "Yahoo Finance", "source_url": None, "facts": {
        "revenue": {"value": 36.8e9, "unit": "EUR", "period_end": "2025-12-31"},
        "operating_cash_flow": {"value": 47e9, "unit": "EUR", "period_end": "2025-12-31"}}},
    "ratios": {"net_margin": 0.1946},
    "market_stats": {"return_3m": -0.1226, "last_close": 183.68},
    "news_items": [{"id": 0, "title": "Bank fined 8 million euros by BaFin", "source": "heise", "date": "2026-11-12",
                    "summary": "", "url": "http://x"}],
}
SOURCES = build_sources(STATE)


def ok(text, ids):
    return check_claim(Claim(text=text, sources=ids), SOURCES)[0] is not None


def test_numbers_in_any_written_form_are_accepted():
    assert ok("Revenue was 36.8 bn EUR in 2025.", ["F:revenue"])       # billions + a year
    assert ok("Net margin was 19.5%.", ["R:net_margin"])                # 0.1946 written as a rounded percent
    assert ok("The share fell 12.3% over 3 months.", ["M:return_3m"])  # sign dropped, "3" is a method number
    assert ok("It was fined 8 million euros on 12 November.", ["N0"])   # number and date from the article


def test_invented_numbers_and_sources_are_dropped():
    assert not ok("Revenue was 41.2 bn EUR.", ["F:revenue"])            # wrong number
    assert not ok("Net margin was 19.5%.", ["F:revenue"])               # right number, wrong source
    assert not ok("Profits rose.", ["F:profit"])                        # source doesn't exist
    assert not ok("Profits rose.", [])                                  # no source at all


def test_unknown_ids_removed_from_kept_claims():
    kept, _ = check_claim(Claim(text="Revenue was 36.8 bn EUR.", sources=["F:revenue", "X:made_up"]), SOURCES)
    assert kept.sources == ["F:revenue"]


def test_bank_hides_misleading_sources():
    bank = build_sources({**STATE, "financial_company": True})
    assert "F:operating_cash_flow" in SOURCES and "F:operating_cash_flow" not in bank


def test_check_memo_report_and_markdown():
    memo = Memo(
        thesis=[Claim(text="Solid company.", sources=["F:revenue"])],
        fundamentals=[Claim(text="Revenue was 36.8 bn EUR.", sources=["F:revenue"]),
                      Claim(text="Revenue was 99 bn EUR.", sources=["F:revenue"])],
        recent_developments=[], technicals=[], risks=[Claim(text="Fines.", sources=["N0"])],
        recommendation="hold", confidence=55,
        recommendation_reason=[Claim(text="Mixed picture.", sources=[])],
    )
    checked, report = check_memo(memo, SOURCES)
    assert report["total"] == 5 and report["kept"] == 3 and report["faithfulness"] == 0.6
    assert checked["confidence"] == 0      # no supported reason left -> no confidence
    md = to_markdown({**STATE, "memo": checked, "citation_report": report,
                      "sources": {k: {"label": v.label, "url": v.url} for k, v in SOURCES.items()}})
    assert "## Sources" in md and "[1]" in md and "3 of 5 claims kept" in md


def test_ids_written_in_the_text_are_not_numbers():
    # Real case from the DBK run: "(N2, N8)" made the checker look for the numbers 2 and 8.
    kept, reason = check_claim(Claim(text="Fined over Postbank IT failures (N0).", sources=[]), SOURCES)
    assert kept is not None, reason
    assert kept.text == "Fined over Postbank IT failures." and kept.sources == ["N0"]
    kept, _ = check_claim(Claim(text="Net margin was 19.5% (R:net_margin).", sources=[]), SOURCES)
    assert kept.sources == ["R:net_margin"]


def test_analyses_are_not_citable():
    kept, _ = check_claim(Claim(text="Risk is high (SPECIALIST ANALYSES:risk).", sources=[]), SOURCES)
    assert kept is None


def test_repeats_and_overlong_sections_dropped():
    same = Claim(text="Revenue was 36.8 bn EUR.", sources=["F:revenue"])
    memo = Memo(
        thesis=[same, Claim(text="Net margin was 19.5%.", sources=["R:net_margin"]),
                Claim(text="Fined 8 million euros.", sources=["N0"])],   # 3rd thesis claim: over the limit of 2
        fundamentals=[same], recent_developments=[], technicals=[], risks=[],
        recommendation="hold", confidence=50, recommendation_reason=[same],
    )
    checked, report = check_memo(memo, SOURCES)
    assert len(checked["thesis"]) == 2 and checked["fundamentals"] == [] and checked["recommendation_reason"] == []
    reasons = {d["reason"] for d in report["dropped"]}
    assert "repeats a sentence from an earlier section" in reasons
    assert "more than 2 claims in this section" in reasons


def test_citations_capped_at_three():
    many = build_sources({**STATE, "news_items": [
        {"id": i, "title": f"Story {chr(65 + i)}", "source": "s", "date": "2026-11-12", "summary": "", "url": None}
        for i in range(6)]})
    kept, _ = check_claim(Claim(text="Lots of news.", sources=[f"N{i}" for i in range(6)]), many)
    assert kept.sources == ["N0", "N1", "N2"]


# ---- from the SAP.DE memo, 24 Nov 2026 ----
SAP = build_sources({**STATE, "market_stats": {"price_vs_ma200": 0.104, "return_1m": -0.147, "volatility_annual": 0.415},
                     "fundamentals_data": {"source": "Yahoo Finance", "source_url": None, "facts": {
                         "stockholders_equity": {"value": 44.6e9, "unit": "EUR", "period_end": "2025-12-31"}}}})


def test_direction_must_match_the_source():
    # Real case: "+10.4% vs the 200-day average" was written as "trading at a discount".
    bad = Claim(text="The share trades at a discount to its 200-day moving average.", sources=["M:price_vs_ma200"])
    kept, reason = check_claim(bad, SAP)
    assert kept is None and "says down/below" in reason
    good = Claim(text="The share trades above its 200-day moving average.", sources=["M:price_vs_ma200"])
    assert check_claim(good, SAP)[0] is not None
    assert check_claim(Claim(text="It fell 14.7% last month.", sources=["M:return_1m"]), SAP)[0] is not None


def test_misspelled_source_ids_are_resolved():
    kept, _ = check_claim(Claim(text="Volatility is 41.5%.", sources=["technicals:volatility_annual"]), SAP)
    assert kept.sources == ["M:volatility_annual"]
    kept, _ = check_claim(Claim(text="Equity is 44.6 bn EUR.", sources=["fundamentals:stockholders_equity"]), SAP)
    assert kept.sources == ["F:stockholders_equity"]
    assert check_claim(Claim(text="Risk is medium.", sources=["risk:overall_risk"]), SAP)[0] is None  # opinions stay out


def test_trimmed_claims_do_not_lower_faithfulness():
    c = lambda t: Claim(text=t, sources=["F:revenue"])
    memo = Memo(thesis=[c("A."), c("B."), c("C.")], fundamentals=[], recent_developments=[], technicals=[],
                risks=[Claim(text="Unsupported.", sources=[])], recommendation="hold", confidence=50,
                recommendation_reason=[c("D.")])
    _, report = check_memo(memo, SOURCES)
    assert report["trimmed"] == 1 and report["unsupported"] == 1
    assert report["faithfulness"] == 0.75   # 3 kept of 4 judged; the trimmed one doesn't count
