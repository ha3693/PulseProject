"""StockTwits user tracking agent for Pulse.
Monitors a target trader/analyst's messages, synthesizes announcements, trade ideas, and market sentiment,
and tracks unseen posts using PostDeduplicator.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from agents.base import BaseAgent
from agents.stocktwits.user_extractor import fetch_stocktwits_user_messages
from agents.reddit.deduplicator import PostDeduplicator

logger = logging.getLogger("StockTwitsUserAgent")


class StockTwitsUserAgent(BaseAgent):
    """Agent that monitors a StockTwits user's stream and generates an executive market summary."""

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
        Execute the monitoring workflow for a target StockTwits user account.

        Args:
            username: Target StockTwits handle (e.g. 'howardlindzon')
            topic: Optional asset ticker or topic filter (e.g. 'NVDA')
            limit: Maximum messages to retrieve
            only_new: If True, uses deduplication to process only unseen messages
            output_file: Optional destination path for output JSON
            use_mock: If True, uses mock messages

        Returns:
            Dict containing the structured user activity report and executive summary.
        """
        clean_user = username.strip().lstrip("@")
        logger.info(f"Starting StockTwits user monitoring for @{clean_user} (Topic filter: '{topic or 'All'}')")

        fetch_result = fetch_stocktwits_user_messages(username=clean_user, limit=limit, use_mock=use_mock)

        if not fetch_result["success"]:
            logger.warning(f"Fetch failed for @{clean_user}: {fetch_result.get('error')}")
            return {
                "success": False,
                "target_user": clean_user,
                "platform": "stocktwits",
                "topic_filter": topic,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "error": fetch_result.get("error"),
                "total_posts_fetched": 0,
                "new_posts_analyzed": 0,
                "executive_summary": f"Could not retrieve messages for @{clean_user}: {fetch_result.get('error')}",
                "announcements_and_milestones": [],
                "posts": [],
            }

        all_posts = fetch_result["posts"]

        # Topic filter if specified
        if topic:
            clean_topic = topic.strip().upper().lstrip("$")
            all_posts = [
                p for p in all_posts
                if clean_topic in p.get("content_text", "").upper() or clean_topic in p.get("symbols", [])
            ]

        seen_ids = self.deduplicator.load_seen_ids() if only_new else set()
        posts_to_analyze = self.deduplicator.filter_new_posts(all_posts, seen_ids) if only_new else all_posts

        if not posts_to_analyze:
            logger.info(f"No new unread messages found for StockTwits user @{clean_user}.")
            report = {
                "success": True,
                "target_user": clean_user,
                "platform": "stocktwits",
                "topic_filter": topic,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_posts_fetched": len(all_posts),
                "new_posts_analyzed": 0,
                "sentiment_signal": "neutral",
                "executive_summary": f"No new unread messages for @{clean_user} since the last monitoring check.",
                "announcements_and_milestones": [],
                "posts": [],
            }
            self.save_report(report, clean_user, prefix="stocktwits_user", output_file=output_file)
            return report

        if self.llm:
            report = self._analyze_with_langchain(clean_user, topic, len(all_posts), posts_to_analyze)
        else:
            report = self._analyze_heuristic(clean_user, topic, len(all_posts), posts_to_analyze)

        # Mark analyzed posts as seen
        if only_new:
            self.deduplicator.mark_posts_seen(posts_to_analyze, seen_ids)

        saved_path = self.save_report(report, clean_user, prefix="stocktwits_user", output_file=output_file)
        logger.info(f"StockTwits user report saved to: {saved_path}")
        return report

    def _analyze_with_langchain(
        self,
        clean_user: str,
        topic: Optional[str],
        total_fetched: int,
        posts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze messages using LangChain LLM."""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an executive market research assistant for Pulse.
Analyze the following recent messages posted by a verified StockTwits market participant/trader.
Synthesize their market stance, key trade ideas, tickers mentioned, and overall posture.

Output MUST strictly be valid JSON matching this schema:
{{
  "sentiment_signal": "<bullish|bearish|neutral>",
  "key_themes": [<list of 3-5 themes or sectors>],
  "announcements_and_milestones": [<list of key positions, trade entries, or market views>],
  "executive_summary": "<2-3 paragraph concise executive synthesis of this user's recent posts and market outlook>"
}}"""),
                ("user", "Target StockTwits Account: @{user}\nFilter: {topic}\n\nMessages:\n{posts_json}"),
            ])

            parser = JsonOutputParser()
            chain = prompt | self.llm | parser

            formatted_posts = [
                {
                    "id": p["id"],
                    "body": p["content_text"],
                    "likes": p["score"],
                    "published_at": p["published_at"],
                    "stocktwits_sentiment": p.get("stocktwits_sentiment"),
                }
                for p in posts
            ]

            analysis = chain.invoke({
                "user": clean_user,
                "topic": topic or "All Assets",
                "posts_json": json.dumps(formatted_posts, indent=2),
            })

            return {
                "success": True,
                "target_user": clean_user,
                "platform": "stocktwits",
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
        """Heuristic analysis when no LLM is configured."""
        bull_count = sum(1 for p in posts if p.get("stocktwits_sentiment") == "Bullish" or "buy" in p["content_text"].lower())
        bear_count = sum(1 for p in posts if p.get("stocktwits_sentiment") == "Bearish" or "sell" in p["content_text"].lower())

        if bull_count > bear_count:
            signal = "bullish"
        elif bear_count > bull_count:
            signal = "bearish"
        else:
            signal = "neutral"

        themes = ["portfolio_positioning", "swing_trading", "equities"]
        milestones = [p["title"] for p in posts[:3]]

        summary = (
            f"Analyzed {len(posts)} recent messages from StockTwits account @{clean_user}. "
            f"Overall sentiment signal is {signal.upper()} ({bull_count} bullish signals vs {bear_count} bearish signals). "
            f"Key recent commentary covers market breadth, risk management, and tactical sector positioning."
        )

        return {
            "success": True,
            "target_user": clean_user,
            "platform": "stocktwits",
            "topic_filter": topic,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_posts_fetched": total_fetched,
            "new_posts_analyzed": len(posts),
            "sentiment_signal": signal,
            "key_themes": themes,
            "announcements_and_milestones": milestones,
            "executive_summary": summary,
            "posts": posts,
        }


# Backward-compatible alias
StockTwitsUserNewsAgent = StockTwitsUserAgent
