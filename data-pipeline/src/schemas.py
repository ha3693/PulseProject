"""Backward compatibility bridge for data-pipeline schemas.
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
