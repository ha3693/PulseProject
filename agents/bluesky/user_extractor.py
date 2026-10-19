"""Bluesky user feed extractor.
Extracts author posts, announcements, and milestones for a target Bluesky handle/actor.
"""

import logging
from typing import Dict, Any, Optional
from agents.bluesky.client import BlueskyClient

logger = logging.getLogger("BlueskyExtractor")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


def fetch_bluesky_user_posts(
    username: str,
    limit: int = 15,
    use_mock: bool = False,
) -> Dict[str, Any]:
    """
    Fetch recent feed posts for a target Bluesky handle.

    Args:
        username: Target Bluesky account handle (e.g. 'bsky.app', 'sama.bsky.social')
        limit: Max posts to retrieve
        use_mock: Force synthetic mock data

    Returns:
        Dict containing success status, username, posts, and optional error.
    """
    clean_user = username.strip().lstrip("@")
    client = BlueskyClient()

    try:
        posts = client.fetch_author_feed(actor=clean_user, limit=limit, use_mock=use_mock)
        return {
            "success": True,
            "username": clean_user,
            "posts": posts,
            "error": None,
        }
    except Exception as err:
        logger.error(f"Failed to extract feed for Bluesky user @{clean_user}: {err}")
        return {
            "success": False,
            "username": clean_user,
            "posts": [],
            "error": str(err),
        }
