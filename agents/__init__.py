"""Pulse Intelligence Agents Package.
Single source of truth for all data pipeline agents.
"""

from agents.base import BaseAgent, get_llm, load_env
from agents.schemas import SignalReport, PostItem, EODMarketContext
from agents.yahoo_finance import YahooFinanceAgent
from agents.reddit import (
    RedditMarketAgent,
    PulseRedditAgent,
    RedditUserAgent,
    RedditUserNewsAgent,
)
from agents.stocktwits import (
    StockTwitsMarketAgent,
    PulseStockTwitsAgent,
    StockTwitsUserAgent,
    StockTwitsUserNewsAgent,
)
from agents.bluesky import (
    BlueskyMarketAgent,
    PulseBlueskyAgent,
    BlueskyUserAgent,
    BlueskyUserNewsAgent,
)

AVAILABLE_AGENTS = {
    "yahoo": YahooFinanceAgent,
    "yahoo-finance": YahooFinanceAgent,
    "yahoo_finance": YahooFinanceAgent,
    "reddit": RedditMarketAgent,
    "reddit-market": RedditMarketAgent,
    "reddit_market": RedditMarketAgent,
    "reddit-user": RedditUserAgent,
    "reddit_user": RedditUserAgent,
    "stocktwits": StockTwitsMarketAgent,
    "stocktwits-market": StockTwitsMarketAgent,
    "stocktwits_market": StockTwitsMarketAgent,
    "stocktwits-user": StockTwitsUserAgent,
    "stocktwits_user": StockTwitsUserAgent,
    "bluesky": BlueskyMarketAgent,
    "bluesky-market": BlueskyMarketAgent,
    "bluesky_market": BlueskyMarketAgent,
    "bluesky-user": BlueskyUserAgent,
    "bluesky_user": BlueskyUserAgent,
}


def get_agent(name: str, **kwargs) -> BaseAgent:
    """Factory function to instantiate an agent by name."""
    norm = name.strip().lower()
    if norm not in AVAILABLE_AGENTS:
        valid = ", ".join(list(AVAILABLE_AGENTS.keys()))
        raise ValueError(f"Unknown agent '{name}'. Available agents: {valid}")
    return AVAILABLE_AGENTS[norm](**kwargs)


__all__ = [
    "BaseAgent",
    "get_llm",
    "load_env",
    "SignalReport",
    "PostItem",
    "EODMarketContext",
    "YahooFinanceAgent",
    "RedditMarketAgent",
    "PulseRedditAgent",
    "RedditUserAgent",
    "RedditUserNewsAgent",
    "StockTwitsMarketAgent",
    "PulseStockTwitsAgent",
    "StockTwitsUserAgent",
    "StockTwitsUserNewsAgent",
    "BlueskyMarketAgent",
    "PulseBlueskyAgent",
    "BlueskyUserAgent",
    "BlueskyUserNewsAgent",
    "AVAILABLE_AGENTS",
    "get_agent",
]
