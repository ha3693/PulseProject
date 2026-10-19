"""StockTwits user stream extractor.
Extracts recent messages, trade ideas, and announcements for a target StockTwits user.
"""

import logging
from typing import Dict, Any, Optional
from agents.stocktwits.client import StockTwitsClient

logger = logging.getLogger("StockTwitsExtractor")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


def fetch_stocktwits_user_messages(
    username: str,
    limit: int = 15,
    use_mock: bool = False,
) -> Dict[str, Any]:
    """
    Fetch recent messages posted by a StockTwits user account.

    Args:
        username: Target StockTwits account handle (e.g. 'howardlindzon')
        limit: Max messages to retrieve
        use_mock: Force synthetic mock data

    Returns:
        Dict containing success status, username, posts, and optional error.
    """
    clean_username = username.strip().lstrip("@")
    client = StockTwitsClient()

    try:
        posts = client.fetch_user_stream(username=clean_username, limit=limit, use_mock=use_mock)
        return {
            "success": True,
            "username": clean_username,
            "posts": posts,
            "error": None,
        }
    except Exception as err:
        logger.error(f"Failed to extract messages for StockTwits user @{clean_username}: {err}")
        return {
            "success": False,
            "username": clean_username,
            "posts": [],
            "error": str(err),
        }
