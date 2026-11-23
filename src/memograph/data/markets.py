"""Which country and stock exchange a ticker belongs to, from its Yahoo suffix,
and which data sources to use there.

AAPL -> United States (no suffix), SAP.DE -> Germany, RELIANCE.NS -> India, 7203.T -> Japan.

To support a new market: add one line to SUFFIXES.
To change where a market's financials come from: edit its `fundamentals_sources`
(tried in order; names are the keys of SOURCES in fundamentals.py).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    country: str
    exchange: str
    news_languages: tuple[str, ...]                 # languages NewsAPI supports for this market
    fundamentals_sources: tuple[str, ...] = ("yahoo",)


EU = ("esef", "yahoo")  # official EU/UK filings first, Yahoo as backup

US = Market("United States", "NYSE / Nasdaq", ("en",), ("edgar",))

SUFFIXES = {
    # Germany: filings.xbrl.org has 0 German filings (checked Nov 2026; the German register has
    # no API for them to collect from), so Yahoo only. Switch back to EU when that changes.
    "DE": Market("Germany", "XETRA", ("de", "en")),
    "F": Market("Germany", "Frankfurt", ("de", "en")),
    "L": Market("United Kingdom", "London Stock Exchange", ("en",), EU),
    "PA": Market("France", "Euronext Paris", ("fr", "en"), EU),
    "AS": Market("Netherlands", "Euronext Amsterdam", ("nl", "en"), EU),
    "MI": Market("Italy", "Borsa Italiana", ("it", "en"), EU),
    "MC": Market("Spain", "Bolsa de Madrid", ("es", "en"), EU),
    "ST": Market("Sweden", "Nasdaq Stockholm", ("sv", "en"), EU),
    "OL": Market("Norway", "Oslo Bors", ("no", "en"), EU),
    "SW": Market("Switzerland", "SIX Swiss Exchange", ("de", "fr", "en")),
    "NS": Market("India", "NSE", ("en",)),
    "BO": Market("India", "BSE", ("en",)),
    "T": Market("Japan", "Tokyo Stock Exchange", ("en",)),
    "HK": Market("Hong Kong", "HKEX", ("zh", "en")),
    "SS": Market("China", "Shanghai Stock Exchange", ("zh", "en")),
    "SZ": Market("China", "Shenzhen Stock Exchange", ("zh", "en")),
    "TO": Market("Canada", "Toronto Stock Exchange", ("en", "fr")),
    "AX": Market("Australia", "ASX", ("en",)),
    "SA": Market("Brazil", "B3", ("pt", "en")),
}


def market_for(ticker: str) -> Market:
    if "." not in ticker:
        return US
    suffix = ticker.rsplit(".", 1)[1].upper()
    if suffix not in SUFFIXES:
        raise ValueError(f"Unknown market suffix '.{suffix}'. Supported: {', '.join(sorted(SUFFIXES))}")
    return SUFFIXES[suffix]


def base_symbol(ticker: str) -> str:
    """'SAP.DE' -> 'SAP'"""
    return ticker.rsplit(".", 1)[0] if "." in ticker else ticker
