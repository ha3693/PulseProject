"""Persistence and deduplication module for Reddit news monitoring.
Maintains a local seen_posts.json file tracking previously processed submission IDs.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Set

logger = logging.getLogger("PostDeduplicator")

DEFAULT_SEEN_FILE = Path(__file__).resolve().parent.parent.parent / "seen_posts.json"


class PostDeduplicator:
    """Tracks seen post IDs across execution runs to ensure only new posts are processed."""

    def __init__(self, storage_path: Path = DEFAULT_SEEN_FILE):
        self.storage_path = Path(storage_path)

    def load_seen_ids(self) -> Set[str]:
        """Load the set of previously processed post IDs."""
        if not self.storage_path.exists():
            return set()
        
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
                elif isinstance(data, dict):
                    return set(data.get("seen_ids", data.keys()))
                return set()
        except Exception as e:
            logger.warning(f"Failed to read seen posts cache from {self.storage_path}: {e}")
            return set()

    def filter_new_posts(
        self,
        posts: List[Dict[str, Any]],
        seen_ids: Set[str]
    ) -> List[Dict[str, Any]]:
        """Filter out any posts that have already been processed in previous runs."""
        new_posts = [p for p in posts if p.get("id") not in seen_ids]
        logger.info(f"Deduplication: {len(new_posts)} new unread posts found out of {len(posts)} total.")
        return new_posts

    def mark_posts_seen(
        self,
        posts: List[Dict[str, Any]],
        seen_ids: Set[str]
    ) -> None:
        """Add new post IDs to the seen storage file."""
        if not posts:
            return

        updated_ids = set(seen_ids)
        for p in posts:
            post_id = p.get("id")
            if post_id:
                updated_ids.add(post_id)

        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "total_seen": len(updated_ids),
                "seen_ids": sorted(list(updated_ids))
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info(f"Updated seen posts store with {len(posts)} new items at {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to write to seen posts file {self.storage_path}: {e}")

    def clear(self) -> None:
        """Clear the seen posts file to re-process from scratch."""
        if self.storage_path.exists():
            self.storage_path.unlink()
            logger.info(f"Cleared seen posts file: {self.storage_path}")
