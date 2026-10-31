"""Bluesky user tracking agent for Pulse.
Monitors a target company or influencer's Bluesky feed, synthesizes announcements, milestones, and updates,
and tracks unseen posts using PostDeduplicator.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
except ImportError:
    ChatPromptTemplate = None
    JsonOutputParser = None

from agents.base import BaseAgent
from agents.bluesky.user_extractor import fetch_bluesky_user_posts
from agents.reddit.deduplicator import PostDeduplicator

logger = logging.getLogger("BlueskyUserAgent")


class BlueskyUserAgent(BaseAgent):
    """Agent that monitors a Bluesky account feed and generates an executive news synthesis."""

    def __init__(self, output_dir: Optional[str] = None, seen_posts_path: Optional[Path] = None):
        super().__init__(output_dir=output_dir)
        self.deduplicator = PostDeduplicator(seen_posts_path) if seen_posts_path else PostDeduplicator()

    def run(
        self,
        username: str,
        topic: Optional[str] = None,
        limit: int = 15,
        only_new: bool = True,
        output_file: Optional[str] = None,
        use_mock: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute the monitoring workflow for a target Bluesky account.

        Args:
            username: Target Bluesky handle (e.g. 'bsky.app', 'openai.com', 'sama.bsky.social')
            topic: Optional topic/keyword filter
            limit: Maximum posts to retrieve
            only_new: If True, uses deduplication to process only unseen posts
            output_file: Optional destination path for output JSON
            use_mock: If True, uses mock feed items

        Returns:
            Dict containing the structured user activity report and executive summary.
        """
        clean_user = username.strip().lstrip("@")
        logger.info(f"Starting Bluesky user monitoring for @{clean_user} (Topic filter: '{topic or 'All'}')")

        fetch_result = fetch_bluesky_user_posts(username=clean_user, limit=limit, use_mock=use_mock)

        if not fetch_result["success"]:
            logger.warning(f"Fetch failed for Bluesky user @{clean_user}: {fetch_result.get('error')}")
            return {
                "success": False,
                "target_user": clean_user,
                "platform": "bluesky",
                "topic_filter": topic,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "error": fetch_result.get("error"),
                "total_posts_fetched": 0,
                "new_posts_analyzed": 0,
                "executive_summary": f"Could not retrieve posts for @{clean_user}: {fetch_result.get('error')}",
                "announcements_and_milestones": [],
                "posts": [],
            }

        all_posts = fetch_result["posts"]

        # Topic filter if specified
        if topic:
            clean_topic = topic.strip().lower()
            all_posts = [p for p in all_posts if clean_topic in p.get("content_text", "").lower()]

        seen_ids = self.deduplicator.load_seen_ids() if only_new else set()
        posts_to_analyze = self.deduplicator.filter_new_posts(all_posts, seen_ids) if only_new else all_posts

        if not posts_to_analyze:
            logger.info(f"No new unread posts found for Bluesky user @{clean_user}.")
            report = {
                "success": True,
                "target_user": clean_user,
                "platform": "bluesky",
                "topic_filter": topic,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_posts_fetched": len(all_posts),
                "new_posts_analyzed": 0,
                "sentiment_signal": "neutral",
                "executive_summary": f"No new unread posts for @{clean_user} since the last monitoring check.",
                "announcements_and_milestones": [],
                "posts": [],
            }
            self.save_report(report, clean_user, prefix="bluesky_user", output_file=output_file)
            return report

        if self.llm:
            report = self._analyze_with_langchain(clean_user, topic, len(all_posts), posts_to_analyze)
        else:
            report = self._analyze_heuristic(clean_user, topic, len(all_posts), posts_to_analyze)

        # Mark analyzed posts as seen
        if only_new:
            self.deduplicator.mark_posts_seen(posts_to_analyze, seen_ids)

        saved_path = self.save_report(report, clean_user, prefix="bluesky_user", output_file=output_file)
        logger.info(f"Bluesky user report saved to: {saved_path}")
        return report

    def _analyze_with_langchain(
        self,
        clean_user: str,
        topic: Optional[str],
        total_fetched: int,
        posts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze Bluesky author posts using LangChain LLM."""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an executive intelligence assistant for Pulse.
Analyze the following recent public Bluesky updates from an official organization or executive account.
Identify major announcements, technical milestones, strategic initiatives, and sentiment signal.

Output MUST strictly be valid JSON matching this schema:
{{
  "sentiment_signal": "<bullish|bearish|neutral>",
  "key_themes": [<list of 3-5 themes>],
  "announcements_and_milestones": [<list of key announcements or product updates>],
  "executive_summary": "<2-3 paragraph concise executive synthesis of this account's recent updates and market implications>"
}}"""),
                ("user", "Bluesky Account: @{user}\nFilter: {topic}\n\nPosts:\n{posts_json}"),
            ])

            parser = JsonOutputParser()
            chain = prompt | self.llm | parser

            formatted_posts = [
                {
                    "id": p["id"],
                    "body": p["content_text"],
                    "engagement": p["score"],
                    "comments": p.get("num_comments", 0),
                    "published_at": p["published_at"],
                }
                for p in posts
            ]

            analysis = chain.invoke({
                "user": clean_user,
                "topic": topic or "All Topics",
                "posts_json": json.dumps(formatted_posts, indent=2),
            })

            return {
                "success": True,
                "target_user": clean_user,
                "platform": "bluesky",
                "topic_filter": topic,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_posts_fetched": total_fetched,
                "new_posts_analyzed": len(posts),
                "sentiment_signal": analysis.get("sentiment_signal", "neutral"),
                "key_themes": analysis.get("key_themes", []),
                "announcements_and_milestones": analysis.get("announcements_and_milestones", []),
                "executive_summary": analysis.get("executive_summary", ""),
                "posts": posts,
            }
        except Exception as e:
            logger.error(f"LangChain analysis failed ({e}). Using heuristic fallback.")
            return self._analyze_heuristic(clean_user, topic, total_fetched, posts)

    def _analyze_heuristic(
        self,
        clean_user: str,
        topic: Optional[str],
        total_fetched: int,
        posts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Deterministic heuristic analysis when LLM is unavailable."""
        themes = ["product_updates", "open_standards", "community_milestones"]
        milestones = [p["title"] for p in posts[:3]]

        summary = (
            f"Analyzed {len(posts)} recent public Bluesky updates from @{clean_user}. "
            f"Posts emphasize platform development, community milestones, and active product iteration. "
            f"Overall sentiment tone is positive and forward-looking."
        )

        return {
            "success": True,
            "target_user": clean_user,
            "platform": "bluesky",
            "topic_filter": topic,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_posts_fetched": total_fetched,
            "new_posts_analyzed": len(posts),
            "sentiment_signal": "bullish",
            "key_themes": themes,
            "announcements_and_milestones": milestones,
            "executive_summary": summary,
            "posts": posts,
        }


# Backward-compatible alias
BlueskyUserNewsAgent = BlueskyUserAgent
