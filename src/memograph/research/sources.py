"""Everything a memo is allowed to cite, each with a short id.

  F:revenue        a figure from the company's annual report
  R:net_margin     a ratio our code calculated from those figures
  M:return_3m      a share-price statistic our code calculated
  N4               news article number 4

The AI's own analyses are NOT sources: they are opinions. A memo claim must point
to the facts underneath them.
"""
import re
from dataclasses import dataclass, field

# For banks these raw figures mislead (cash flows swing with deposits and loans).
BANK_HIDDEN_FACTS = {"operating_cash_flow", "capex", "long_term_debt"}

NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    out = []
    for m in NUM_RE.findall(text):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


@dataclass
class Source:
    id: str
    label: str                                       # shown to the AI and in the reference list
    numbers: list[float] = field(default_factory=list)  # raw values a claim may quote
    url: str | None = None


def money(v: float, unit: str) -> str:
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.1f} bn {unit}"
    if a >= 1e6:
        return f"{v / 1e6:.1f} mn {unit}"
    return f"{v:,.0f} {unit}"


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _name(key: str) -> str:
    return key.replace("_", " ")


def build_sources(state: dict) -> dict[str, Source]:
    out: dict[str, Source] = {}
    fd = state.get("fundamentals_data")
    unit = "?"
    if fd:
        hidden = BANK_HIDDEN_FACTS if state.get("financial_company") else set()
        for k, f in fd["facts"].items():
            if k in hidden:
                continue
            unit = f["unit"]
            label = f"{_name(k)}: {money(f['value'], f['unit'])} (year ending {f['period_end']}, {fd['source']})"
            out[f"F:{k}"] = Source(f"F:{k}", label, [f["value"]], fd.get("source_url"))
    for k, x in (state.get("ratios") or {}).items():
        shown = money(x, unit) if k == "free_cash_flow" else pct(x)
        out[f"R:{k}"] = Source(f"R:{k}", f"{_name(k)}: {shown} (calculated from the annual figures)", [x])
    for k, x in (state.get("market_stats") or {}).items():
        if k in ("last_close", "ma50", "ma200"):
            shown = f"{x:.2f}"
        elif k == "days_of_data":
            shown = f"{int(x)}"
        else:
            shown = pct(x)
        out[f"M:{k}"] = Source(f"M:{k}", f"share price {_name(k)}: {shown} (last 12 months)", [x])
    for it in state.get("news_items") or []:
        sid = f"N{it['id']}"
        label = f"\"{it['title']}\" ({it['source']}, {it['date']})"
        nums = numbers_in(f"{it['title']} {it.get('summary', '')}")
        out[sid] = Source(sid, label, nums, it.get("url"))
    return out
