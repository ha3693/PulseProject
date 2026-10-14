"""Backward compatibility bridge for yahoo_finance_extractor.
Re-exports from agents.yahoo_finance.extractor.
"""

from agents.yahoo_finance.extractor import (
    fetch_yahoo_finance_news,
    fetch_eod_market_data,
    resolve_topic_to_symbol,
    KNOWN_TOPIC_MAPPINGS,
)

__all__ = [
    "fetch_yahoo_finance_news",
    "fetch_eod_market_data",
    "resolve_topic_to_symbol",
    "KNOWN_TOPIC_MAPPINGS",
]
