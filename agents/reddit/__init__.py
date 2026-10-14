"""Reddit Agents Package for Pulse."""

from agents.reddit.market_agent import RedditMarketAgent, PulseRedditAgent
from agents.reddit.user_agent import RedditUserAgent, RedditUserNewsAgent
from agents.reddit.client import RedditClient, TARGET_SUBREDDITS
from agents.reddit.user_extractor import fetch_user_submissions
from agents.reddit.deduplicator import PostDeduplicator

__all__ = [
    "RedditMarketAgent",
    "PulseRedditAgent",
    "RedditUserAgent",
    "RedditUserNewsAgent",
    "RedditClient",
    "TARGET_SUBREDDITS",
    "fetch_user_submissions",
    "PostDeduplicator",
]
