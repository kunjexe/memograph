"""The research memo: its shape, the citation checker, and the Markdown version.

The checker is plain code, no AI. A claim survives only if:
  1. it cites at least one source id that really exists, and
  2. every number in its text appears in one of the sources it cites
     (allowing for rounding and for 0.195 being written as 19.5%).
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

from memograph.research.sources import Source, numbers_in

SECTIONS = ["thesis", "fundamentals", "recent_developments", "technicals", "risks", "recommendation_reason"]
TITLES = {
    "thesis": "Thesis", "fundamentals": "Fundamentals", "recent_developments": "Recent developments",
    "technicals": "Share price", "risks": "Risks", "recommendation_reason": "Why this view",
}
# Numbers that describe the method, not a fact: "3-month return", "50-day average", "12 months".
STRUCTURAL = {1, 3, 6, 12, 20, 30, 50, 52, 200}
# Most claims a section may keep (the model sometimes writes far more than asked).
MAX_CITATIONS = 3  # a claim citing 11 articles is padding, not evidence: keep the first 3 real ones
LIMITS = {"thesis": 2, "fundamentals": 4, "recent_developments": 4, "technicals": 3, "risks": 4, "recommendation_reason": 3}
ID_RE = re.compile(r"\b(?:[FRM]:[a-z0-9_]+|N\d+)\b")
# "(R:net_margin)", "(N11, N12)", "(SPECIALIST ANALYSES:risk)": ids written into the sentence itself
ID_BRACKETS_RE = re.compile(r"\s*\((?:[^()]*?(?:\b[FRM]:[a-z0-9_]+|\bN\d+\b|SPECIALIST)[^()]*?)\)")


# The model sometimes names a real source in its own words: "technicals:volatility_annual" means M:volatility_annual.
PREFIX_ALIASES = {
    "fundamentals": ("F", "R"), "fundamental": ("F", "R"), "facts": ("F",), "ratios": ("R",), "ratio": ("R",),
    "market": ("M",), "technicals": ("M",), "technical": ("M",), "price": ("M",), "share_price": ("M",),
}
# Statistics with a direction: a sentence saying "below" must not cite a positive value, and vice versa.
SIGNED = {"M:price_vs_ma50", "M:price_vs_ma200", "M:return_1m", "M:return_3m", "M:return_6m", "M:return_period"}
DOWN_WORDS = {"below", "discount", "decline", "declined", "declining", "fell", "fall", "falling", "drop", "dropped",
              "negative", "down", "lower", "loss", "losses", "under"}
UP_WORDS = {"above", "premium", "rose", "rise", "rising", "gain", "gained", "gains", "increase", "increased",
            "positive", "up", "higher", "over"}


def resolve_id(sid: str, sources: dict[str, Source]) -> str | None:
    """'technicals:volatility_annual' -> 'M:volatility_annual' if that source exists; unknown -> None.
    Only spelling is repaired: the claim's numbers are still checked against the real source."""
    if sid in sources:
        return sid
    name = sid
    prefixes: tuple[str, ...] = ("F", "R", "M")
    if ":" in sid:
        prefix, name = sid.split(":", 1)
        prefixes = PREFIX_ALIASES.get(prefix.strip().lower().replace(" ", "_"), ())
    name = name.strip().lower().replace(" ", "_")
    for p in prefixes:
        if f"{p}:{name}" in sources:
            return f"{p}:{name}"
    return None


def direction_conflict(text: str, valid: list[str], sources: dict[str, Source]) -> str | None:
    if len(valid) != 1 or valid[0] not in SIGNED or not sources[valid[0]].numbers:
        return None  # only judged when one directional statistic is cited alone
    v = sources[valid[0]].numbers[0]
    words = set(re.findall(r"[a-z]+", text.lower()))
    if v > 0 and words & DOWN_WORDS and not words & UP_WORDS:
        return f"says down/below, but {valid[0]} is +{v * 100:.1f}%"
    if v < 0 and words & UP_WORDS and not words & DOWN_WORDS:
        return f"says up/above, but {valid[0]} is {v * 100:.1f}%"
    return None


def split_ids(text: str) -> tuple[str, list[str]]:
    """Moves source ids the model wrote into the sentence out of it: (clean text, ids found)."""
    ids = ID_RE.findall(" ".join(m.group(0) for m in ID_BRACKETS_RE.finditer(text)))
    clean = ID_BRACKETS_RE.sub("", text).strip()
    return clean, ids


class Claim(BaseModel):
    text: str = Field(description="one sentence; copy any number exactly as written in the source")
    sources: list[str] = Field(description="ids of the sources that support this sentence, e.g. ['F:revenue', 'N3']")


class Memo(BaseModel):
    thesis: list[Claim] = Field(description="1-2 claims: the main investment view")
    fundamentals: list[Claim] = Field(description="2-4 claims about the financial figures")
    recent_developments: list[Claim] = Field(description="0-4 claims about the news, citing N ids")
    technicals: list[Claim] = Field(description="1-3 claims about the share price, citing M ids")
    risks: list[Claim] = Field(description="2-4 claims about the main risks")
    recommendation: Literal["buy", "hold", "sell"]
    confidence: int = Field(ge=0, le=100, description="how sure you are, 0-100")
    recommendation_reason: list[Claim] = Field(description="1-3 claims explaining the recommendation")


def _candidates(src: Source) -> set[float]:
    """All the ways a source's numbers could legitimately appear in a sentence."""
    out = set()
    for n in src.numbers + numbers_in(src.label):
        for v in (n, n * 100, n / 1e9, n / 1e6, n / 1e3):
            out.add(abs(v))
    return out


def _supported(n: float, candidates: set[float]) -> bool:
    a = abs(n)
    return any(abs(a - c) <= max(0.051, 0.01 * c) for c in candidates)


def check_claim(claim: Claim, sources: dict[str, Source]) -> tuple[Claim | None, str]:
    text, ids_in_text = split_ids(claim.text)  # ids like "(N2, N8)" are not numbers to verify
    cited = list(dict.fromkeys(claim.sources + ids_in_text))
    claim = Claim(text=text, sources=cited)
    valid = list(dict.fromkeys(r for r in (resolve_id(s, sources) for s in claim.sources) if r))
    if not valid:
        return None, f"cites no real source ({claim.sources or 'none'})"
    if conflict := direction_conflict(text, valid, sources):
        return None, conflict
    candidates = set().union(*(_candidates(sources[s]) for s in valid))
    for n in numbers_in(claim.text):
        if n == int(n) and (1900 <= n <= 2100 or n in STRUCTURAL):
            continue  # a year, or a method number like "50-day"
        if not _supported(n, candidates):
            return None, f"the number {n:g} is not in its sources {valid}"
    return Claim(text=claim.text, sources=valid[:MAX_CITATIONS]), "ok"


def check_memo(memo: Memo, sources: dict[str, Source]) -> tuple[dict, dict]:
    """Returns (checked memo as dict, report)."""
    checked, dropped, total, seen = memo.model_dump(), [], 0, set()
    for section in SECTIONS:
        kept = []
        for claim in getattr(memo, section):
            total += 1
            ok, reason = check_claim(claim, sources)
            key = " ".join(ok.text.lower().split()) if ok else None
            kind = "unsupported"
            if ok and key in seen:
                ok, reason, kind = None, "repeats a sentence from an earlier section", "trimmed"
            elif ok and len(kept) >= LIMITS[section]:
                ok, reason, kind = None, f"more than {LIMITS[section]} claims in this section", "trimmed"
            if ok:
                seen.add(key)
                kept.append(ok.model_dump())
            else:
                dropped.append({"section": section, "text": claim.text, "reason": reason, "kind": kind})
        checked[section] = kept
    if not checked["recommendation_reason"]:
        checked["confidence"] = 0  # a view with no supported reason is worth nothing
    kept_n = total - len(dropped)
    trimmed = sum(d["kind"] == "trimmed" for d in dropped)
    judged = total - trimmed  # repeats and over-limit claims say nothing about truthfulness
    report = {"total": total, "kept": kept_n, "unsupported": len(dropped) - trimmed, "trimmed": trimmed,
              "dropped": dropped, "faithfulness": round(kept_n / judged, 3) if judged else 0.0}
    return checked, report


def to_markdown(state: dict) -> str:
    memo, sources, report = state["memo"], state.get("sources", {}), state.get("citation_report", {})
    numbering: dict[str, int] = {}

    def refs(ids: list[str]) -> str:
        for i in ids:
            numbering.setdefault(i, len(numbering) + 1)
        return "".join(f"[{numbering[i]}]" for i in ids)

    lines = [
        f"# {state.get('company_name')} ({state['ticker']}): research memo",
        "",
        f"As of {state.get('as_of') or 'today'} · **{memo['recommendation'].upper()}**, confidence "
        f"{memo['confidence']}/100 · AI-generated for a portfolio project, not investment advice.",
    ]
    for section in SECTIONS:
        claims = memo.get(section) or []
        if claims:
            lines += ["", f"## {TITLES[section]}", ""]
            lines += [f"- {c['text']} {refs(c['sources'])}" for c in claims]
    lines += ["", "## Sources", ""]
    for sid, n in numbering.items():
        s = sources.get(sid, {})
        link = f" <{s['url']}>" if s.get("url") else ""
        lines.append(f"{n}. {s.get('label', sid)}{link}")
    if report:
        lines += ["", "## Citation check", "",
                  f"{report['kept']} of {report['total']} claims kept. Faithfulness {report['faithfulness'] * 100:.0f}% "
                  f"({report.get('unsupported', 0)} unsupported, {report.get('trimmed', 0)} trimmed for length or repetition)."]
        lines += [f"- Dropped ({d['section']}, {d.get('kind', 'unsupported')}): \"{d['text']}\" ({d['reason']})"
                  for d in report["dropped"]]
    return "\n".join(lines) + "\n"
