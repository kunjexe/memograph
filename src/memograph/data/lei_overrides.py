"""Manual ticker -> LEI links.

European filings identify companies by LEI (Legal Entity Identifier, a 20-character
code), not by ticker. esef.py finds the LEI automatically. If it ever picks the
wrong company, look the right one up at https://search.gleif.org and add it here.
"""
LEI_OVERRIDES: dict[str, str] = {
    # "SAP.DE": "<20-character LEI from search.gleif.org>",
}
