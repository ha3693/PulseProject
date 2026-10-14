"""Backward compatibility bridge for schemas.
Re-exports from agents.schemas.
"""

from agents.schemas import (
    SignalReport,
    PostItem,
    EODMarketContext,
    RedditSignalReport,
    YahooFinanceSignalReport,
    RedditPostItem,
    YahooNewsItem,
)

__all__ = [
    "SignalReport",
    "PostItem",
    "EODMarketContext",
    "RedditSignalReport",
    "YahooFinanceSignalReport",
    "RedditPostItem",
    "YahooNewsItem",
]
