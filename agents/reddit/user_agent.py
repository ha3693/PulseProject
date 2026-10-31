"""LangChain-powered AI news monitoring agent for tracking Reddit user submissions.
Fetches from Reddit's public endpoint without requiring OAuth or API keys.
Extracts announcements, milestones, and synthesizes structured executive summaries.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    from langchain_core.tools import tool
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
except ImportError:
    def tool(fn):
        return fn
    ChatPromptTemplate = None
    JsonOutputParser = None

from agents.base import BaseAgent
from agents.reddit.user_extractor import fetch_user_submissions
from agents.reddit.deduplicator import PostDeduplicator

logger = logging.getLogger("RedditUserAgent")


@tool
def extract_reddit_user_posts(username: str, limit: int = 10) -> str:
    """Fetch recent Reddit submissions for a specified user from the public endpoint."""
    res = fetch_user_submissions(username=username, limit=limit)
    return json.dumps(res)


class RedditUserAgent(BaseAgent):
    """Agent that monitors a Reddit user's submissions and generates an executive news synthesis."""

    def __init__(self, output_dir: Optional[str] = None, seen_posts_path: Optional[Path] = None):
        super().__init__(output_dir=output_dir)
        self.deduplicator = PostDeduplicator(seen_posts_path) if seen_posts_path else PostDeduplicator()

    def run(
        self,
        username: str,
        topic: Optional[str] = None,
        limit: int = 10,
        only_new: bool = True,
        output_file: Optional[str] = None,
        use_mock: bool = False
    ) -> Dict[str, Any]:
        """
        Execute the news monitoring workflow for a target Reddit user.
        
        Args:
            username: Target Reddit account username (e.g. 'OpenAI', 'sama', 'spez')
            topic: Optional focus area or news theme (e.g. 'AI', 'earnings', 'product updates')
            limit: Maximum submissions to retrieve
            only_new: If True, uses deduplication to process only unseen posts
            output_file: Optional destination path for output JSON
            use_mock: If True, uses mock submissions for testing/demo

        Returns:
            Dict containing the structured news report and executive summary.
        """
        clean_user = username.strip().lstrip("u/").lstrip("/u/")
        logger.info(f"Starting news monitoring run for target user: u/{clean_user} (Topic filter: '{topic or 'All'}')")

        fetch_result = fetch_user_submissions(username=clean_user, limit=limit, use_mock=use_mock)
        
        if not fetch_result["success"]:
            logger.warning(f"Fetch failed: {fetch_result.get('error')}")
            return {
                "success": False,
                "target_user": clean_user,
                "topic_filter": topic,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "error": fetch_result.get("error"),
                "total_posts_fetched": 0,
                "new_posts_analyzed": 0,
                "executive_summary": f"Could not retrieve posts for u/{clean_user}: {fetch_result.get('error')}",
                "announcements_and_milestones": [],
                "posts": []
            }

        all_posts = fetch_result["posts"]
        seen_ids = self.deduplicator.load_seen_ids() if only_new else set()
        posts_to_analyze = self.deduplicator.filter_new_posts(all_posts, seen_ids) if only_new else all_posts

        if not posts_to_analyze:
            logger.info(f"No new unread submissions found for u/{clean_user}.")
            report = {
                "success": True,
                "target_user": clean_user,
                "topic_filter": topic,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_posts_fetched": len(all_posts),
                "new_posts_analyzed": 0,
                "executive_summary": f"No new unread posts for u/{clean_user} since the last monitoring check.",
                "announcements_and_milestones": [],
                "posts": []
            }
            self.save_report(report, clean_user, prefix="reddit_user", output_file=output_file)
            return report

        if self.llm:
            analysis = self._analyze_with_llm(clean_user, topic, posts_to_analyze)
        else:
            analysis = self._analyze_heuristic(clean_user, topic, posts_to_analyze)

        if only_new:
            self.deduplicator.mark_posts_seen(posts_to_analyze, seen_ids)

        report = {
            "success": True,
            "target_user": clean_user,
            "topic_filter": topic,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_posts_fetched": len(all_posts),
            "new_posts_analyzed": len(posts_to_analyze),
            "executive_summary": analysis.get("executive_summary", ""),
            "sentiment_signal": analysis.get("sentiment_signal", "neutral"),
            "announcements_and_milestones": analysis.get("announcements_and_milestones", []),
            "key_themes": analysis.get("key_themes", []),
            "posts": analysis.get("posts", posts_to_analyze)
        }

        saved_path = self.save_report(report, clean_user, prefix="reddit_user", output_file=output_file)
        logger.info(f"Executive summary successfully exported to: {saved_path}")
        return report

    def _analyze_with_llm(
        self,
        username: str,
        topic: Optional[str],
        posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Use LangChain to extract announcements, filter for topic, and synthesize executive summary."""
        try:
            topic_instruction = (
                f"Specifically prioritize items relevant to the focus topic: '{topic}'."
                if topic else "Extract all notable news, updates, announcements, and opinions."
            )

            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an AI intelligence and news monitoring agent for Pulse.
Your task is to analyze recent submissions from Reddit user u/{username} and synthesize an executive-level summary.

Instructions:
1. {topic_instruction}
2. Extract key milestones, product announcements, official statements, or significant opinion shifts.
3. Classify the overall tone / sentiment signal ('positive/bullish', 'neutral', 'negative/bearish').
4. For each post, summarize the key takeaway and tag whether it represents an official announcement or discussion.

Return STRICT JSON matching this structure:
{{
  "executive_summary": "<2-3 paragraph executive synthesis of what u/{username} shared>",
  "sentiment_signal": "<positive|neutral|negative>",
  "key_themes": ["<theme1>", "<theme2>"],
  "announcements_and_milestones": [
    "<bullet point 1 with date/detail>",
    "<bullet point 2 with date/detail>"
  ],
  "posts": [
    {{
      "id": "<id>",
      "title": "<title>",
      "subreddit": "<subreddit>",
      "created_at": "<created_at>",
      "permalink": "<permalink>",
      "external_url": "<external_url>",
      "score": <score>,
      "summary": "<1-2 sentence core insight>",
      "is_announcement": <true/false>,
      "relevance_to_topic": <true/false>
    }}
  ]
}}"""),
                ("user", "User: u/{username}\nTopic Focus: {topic}\nSubmissions:\n{posts_json}")
            ])

            posts_snippet = [
                {
                    "id": p.get("id"),
                    "title": p.get("title"),
                    "subreddit": p.get("subreddit"),
                    "created_at": p.get("created_at"),
                    "permalink": p.get("permalink"),
                    "external_url": p.get("external_url"),
                    "score": p.get("score"),
                    "body": p.get("body", "")[:600]
                }
                for p in posts
            ]

            chain = prompt | self.llm | JsonOutputParser()
            result = chain.invoke({
                "username": username,
                "topic": topic or "General News & Announcements",
                "topic_instruction": topic_instruction,
                "posts_json": json.dumps(posts_snippet, indent=2)
            })
            return result

        except Exception as e:
            logger.error(f"LLM synthesis failed ({e}). Falling back to heuristic summary.")
            return self._analyze_heuristic(username, topic, posts)

    def _analyze_heuristic(
        self,
        username: str,
        topic: Optional[str],
        posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Deterministic heuristic fallback when LLM is unavailable."""
        announcements = []
        parsed_posts = []

        for p in posts:
            title = p.get("title", "")
            sub = p.get("subreddit", "")
            announcements.append(f"[{sub}] {title}")
            parsed_posts.append({
                "id": p.get("id"),
                "title": title,
                "subreddit": sub,
                "created_at": p.get("created_at"),
                "permalink": p.get("permalink"),
                "external_url": p.get("external_url"),
                "score": p.get("score", 0),
                "summary": title,
                "is_announcement": any(w in title.lower() for w in ["launch", "announce", "update", "release", "new"]),
                "relevance_to_topic": True if not topic else (topic.lower() in (title + p.get("body", "")).lower())
            })

        return {
            "executive_summary": f"Recent submissions from u/{username} across {len(posts)} posts. Key activity observed in {', '.join(set(p.get('subreddit', '') for p in posts))}.",
            "sentiment_signal": "neutral",
            "key_themes": ["reddit_submissions", "public_updates"],
            "announcements_and_milestones": announcements[:5],
            "posts": parsed_posts
        }


# Backward compatibility alias
RedditUserNewsAgent = RedditUserAgent
