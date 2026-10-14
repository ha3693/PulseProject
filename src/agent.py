"""Backward compatibility bridge for RedditUserNewsAgent.
Re-exports from agents.reddit.user_agent.
"""

from agents.reddit.user_agent import (
    RedditUserAgent,
    RedditUserNewsAgent,
    extract_reddit_user_posts,
)
from agents.base import get_llm

__all__ = ["RedditUserAgent", "RedditUserNewsAgent", "extract_reddit_user_posts", "get_llm"]
