"""Pulse Bluesky Market Signal Agent using LangChain.
Queries real-time Bluesky public posts and conversational microblogging sentiment for assets/topics,
extracts themes, catalysts, and risks, and outputs structured JSON reports conforming to Pulse SignalReport schema.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
except ImportError:
    ChatPromptTemplate = None
    JsonOutputParser = None

from agents.base import BaseAgent
from agents.schemas import SignalReport, PostItem
from agents.bluesky.client import BlueskyClient

logger = logging.getLogger("BlueskyMarketAgent")


class BlueskyMarketAgent(BaseAgent):
    """Agent orchestrator for retrieving Bluesky discussions and generating analytical JSON signals."""

    def __init__(self, output_dir: Optional[str] = None):
        super().__init__(output_dir=output_dir)
        self.client = BlueskyClient()

    def run(
        self,
        topic: str,
        time_window: str = "week",
        limit: int = 15,
        output_file: Optional[str] = None,
        use_mock: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute the query on Bluesky for a given asset, brand, or topic.
        Enriches posts with sentiment and outputs a validated JSON report.
        """
        clean_topic = topic.strip()
        logger.info(f"Initiating Bluesky search for topic: '{clean_topic}' (limit: {limit})")

        raw_posts = self.client.search_posts(
            query=clean_topic,
            limit=limit,
            use_mock=use_mock,
        )

        if not raw_posts:
            logger.warning(f"No posts retrieved for '{clean_topic}' on Bluesky.")
            empty_report = SignalReport(
                topic=clean_topic,
                time_window=time_window,
                subreddits_scanned=[f"bluesky/{clean_topic}"],
                total_posts_retrieved=0,
                relevant_posts_count=0,
                aggregate_sentiment_score=0.0,
                synthesis=f"No recent public posts found for '{clean_topic}' across Bluesky in the selected time window.",
                posts=[],
            )
            report_dict = empty_report.to_dict()
            self.save_report(report_dict, clean_topic, prefix="bluesky", output_file=output_file)
            return report_dict

        # Process and enrich messages with FinBERT
        raw_posts = self.score_posts_with_finbert(raw_posts)
        finbert_stats = self.finbert.compute_aggregate(raw_posts) if (self.finbert and self.finbert.is_loaded) else None

        # Process and enrich messages with LLM or FinBERT
        if self.llm:
            report_dict = self._process_with_langchain(clean_topic, time_window, raw_posts, finbert_stats)
        else:
            logger.info("Running FinBERT sequence classification scoring engine on Bluesky posts.")
            report_dict = self._process_heuristic(clean_topic, time_window, raw_posts, finbert_stats)

        saved_path = self.save_report(report_dict, clean_topic, prefix="bluesky", output_file=output_file)
        logger.info(f"Bluesky signal report successfully saved to: {saved_path}")
        return report_dict

    def _process_with_langchain(
        self,
        topic: str,
        time_window: str,
        raw_posts: List[Dict[str, Any]],
        finbert_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Use LangChain with structured prompt to classify sentiment and synthesize findings."""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an institutional financial and market sentiment analyst for Pulse.
Your task is to analyze conversational microblogging posts from Bluesky regarding a specific topic, brand, or financial asset.

Guidelines:
1. Relevance: Verify each post genuinely discusses the intended asset/brand '{topic}'. Filter out coincidental matches (e.g. fruit vs Apple, color vs Gold).
2. Financial & Tech Sentiment: Classify each post as positive, neutral, or negative, and score between -100.0 (bearish/negative) and +100.0 (bullish/positive).
3. Catalysts & Themes: Highlight developer reception, product feedback, corporate governance, and macro implications.

Output MUST strictly be valid JSON matching this schema:
{{
  "topic": "{topic}",
  "aggregate_sentiment_score": <float between -100.0 and 100.0>,
  "sentiment_breakdown": {{"positive": <int>, "neutral": <int>, "negative": <int>}},
  "top_themes": [<list of top 3-5 themes>],
  "key_positive_catalysts": [<list of 2-3 positive drivers or praise>],
  "key_risk_factors": [<list of 2-3 risks, critiques, or concerns>],
  "synthesis": "<2-3 paragraph executive summary of public and tech community sentiment on Bluesky>",
  "posts": [
    {{
      "id": "<id>",
      "subreddit": "<source_channel>",
      "title": "<title>",
      "url": "<url>",
      "permalink": "<permalink>",
      "published_at": "<published_at>",
      "score": <score>,
      "num_comments": <num_comments>,
      "upvote_ratio": 1.0,
      "content_text": "<content_text>",
      "is_relevant": <true/false>,
      "sentiment_label": "<positive|neutral|negative>",
      "confidence": <float between 0.0 and 1.0>,
      "sentiment_score": <float between -100.0 and 100.0>,
      "theme_tags": [<list of tags>],
      "relevance_reason": "<brief rationale>"
    }}
  ]
}}"""),
                ("user", "Analyze these Bluesky posts for topic '{topic}':\n\n{posts_json}"),
            ])

            parser = JsonOutputParser()
            chain = prompt | self.llm | parser

            formatted_posts = [
                {
                    "id": p["id"],
                    "body": p["content_text"],
                    "finbert_score": p.get("finbert_score"),
                    "finbert_label": p.get("finbert_label"),
                    "engagement": p["score"],
                    "comments": p.get("num_comments", 0),
                    "published_at": p["published_at"],
                }
                for p in raw_posts
            ]

            result = chain.invoke({
                "topic": topic,
                "posts_json": json.dumps(formatted_posts, indent=2),
            })

            posts_map = {p["id"]: p for p in raw_posts}
            enriched_posts = []
            for p in result.get("posts", []):
                orig = posts_map.get(p.get("id"), {})
                enriched_posts.append(PostItem(
                    id=p.get("id", orig.get("id", "")),
                    subreddit=p.get("subreddit", orig.get("subreddit", f"bluesky/{topic}")),
                    title=p.get("title", orig.get("title", "")),
                    url=orig.get("url", p.get("url", "")),
                    permalink=orig.get("permalink", p.get("permalink", "")),
                    published_at=orig.get("published_at", p.get("published_at", datetime.now(timezone.utc).isoformat())),
                    score=orig.get("score", p.get("score", 0)),
                    num_comments=orig.get("num_comments", p.get("num_comments", 0)),
                    upvote_ratio=1.0,
                    content_text=orig.get("content_text", p.get("content_text", "")),
                    is_relevant=p.get("is_relevant", True),
                    sentiment_label=p.get("sentiment_label", "neutral"),
                    confidence=float(p.get("confidence", 0.8)),
                    sentiment_score=float(p.get("sentiment_score", 0.0)),
                    finbert_label=orig.get("finbert_label"),
                    finbert_score=orig.get("finbert_score"),
                    finbert_confidence=orig.get("finbert_confidence"),
                    theme_tags=p.get("theme_tags", []),
                    relevance_reason=p.get("relevance_reason"),
                ))

            report = SignalReport(
                topic=topic,
                time_window=time_window,
                subreddits_scanned=[f"bluesky/{topic}"],
                total_posts_retrieved=len(raw_posts),
                relevant_posts_count=len([p for p in enriched_posts if p.is_relevant]),
                aggregate_sentiment_score=float(result.get("aggregate_sentiment_score", 0.0)),
                sentiment_breakdown=result.get("sentiment_breakdown", {"positive": 0, "neutral": 0, "negative": 0}),
                finbert_aggregate_score=finbert_stats.get("aggregate_score") if finbert_stats else None,
                finbert_breakdown=finbert_stats.get("breakdown") if finbert_stats else None,
                scoring_engine="hybrid (FinBERT + LLM)" if finbert_stats else "LLM",
                top_themes=result.get("top_themes", []),
                key_positive_catalysts=result.get("key_positive_catalysts", []),
                key_risk_factors=result.get("key_risk_factors", []),
                synthesis=result.get("synthesis", ""),
                posts=enriched_posts,
            )
            return report.to_dict()

        except Exception as e:
            logger.error(f"LangChain processing failed ({e}). Falling back to heuristic engine.")
            return self._process_heuristic(topic, time_window, raw_posts, finbert_stats)

    def _process_heuristic(
        self,
        topic: str,
        time_window: str,
        raw_posts: List[Dict[str, Any]],
        finbert_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deterministic scoring fallback for Bluesky discussions utilizing FinBERT."""
        pos_words = {"growth", "breakthrough", "innovative", "impressive", "bullish", "strong", "lead", "outperform", "success"}
        neg_words = {"concern", "flaw", "risk", "lawsuit", "decline", "slowdown", "bearish", "monopoly", "drop", "failure"}

        scored_posts = []
        pos_count = 0
        neg_count = 0
        neu_count = 0
        total_score = 0.0

        for p in raw_posts:
            if "finbert_score" in p and p["finbert_score"] is not None:
                score = float(p["finbert_score"])
                label = p.get("finbert_label", "neutral")
                confidence = float(p.get("finbert_confidence", 0.85))
                if label == "positive":
                    pos_count += 1
                elif label == "negative":
                    neg_count += 1
                else:
                    neu_count += 1
            else:
                text = p["content_text"].lower()
                words = set(text.split())

                p_hits = len(words & pos_words)
                n_hits = len(words & neg_words)

                if p_hits > n_hits:
                    score = min(25.0 + p_hits * 18.0, 85.0)
                    label = "positive"
                    pos_count += 1
                elif n_hits > p_hits:
                    score = max(-25.0 - n_hits * 18.0, -85.0)
                    label = "negative"
                    neg_count += 1
                else:
                    score = 0.0
                    label = "neutral"
                    neu_count += 1
                confidence = 0.75

            total_score += score
            scored_posts.append(PostItem(
                id=p["id"],
                subreddit=p["subreddit"],
                title=p["title"],
                url=p["url"],
                permalink=p["permalink"],
                published_at=p["published_at"],
                score=p["score"],
                num_comments=p.get("num_comments", 0),
                upvote_ratio=1.0,
                content_text=p["content_text"],
                is_relevant=True,
                sentiment_label=label,
                confidence=confidence,
                sentiment_score=score,
                finbert_label=p.get("finbert_label"),
                finbert_score=p.get("finbert_score"),
                finbert_confidence=p.get("finbert_confidence"),
                theme_tags=["tech_innovation" if "architecture" in p["content_text"] or "developer" in p["content_text"] else "community_feedback"],
                relevance_reason="Queried keyword match",
            ))

        avg_score = round(total_score / max(len(raw_posts), 1), 1)

        synthesis = (
            f"Evaluated {len(raw_posts)} recent Bluesky posts discussing '{topic}'. "
            f"Sentiment index sits at {avg_score:+.1f} (-100 to +100), with {pos_count} positive, {neg_count} negative, and {neu_count} neutral posts. "
            f"The community discourse primarily highlights product execution, ecosystem dynamics, and competitive moats."
        )

        report = SignalReport(
            topic=topic,
            time_window=time_window,
            subreddits_scanned=[f"bluesky/{topic}"],
            total_posts_retrieved=len(raw_posts),
            relevant_posts_count=len(raw_posts),
            aggregate_sentiment_score=avg_score,
            sentiment_breakdown={"positive": pos_count, "neutral": neu_count, "negative": neg_count},
            finbert_aggregate_score=finbert_stats.get("aggregate_score") if finbert_stats else avg_score,
            finbert_breakdown=finbert_stats.get("breakdown") if finbert_stats else {"positive": pos_count, "neutral": neu_count, "negative": neg_count},
            scoring_engine="FinBERT (ProsusAI/finbert)" if (self.finbert and self.finbert.is_loaded) else "heuristic_rules",
            top_themes=["product_moat", "developer_adoption", "competitive_positioning"],
            key_positive_catalysts=[f"Strong developer affinity and positive feedback for {topic}", "Expanding enterprise and consumer mindshare"],
            key_risk_factors=["Competitive alternatives emerging across peers", "Potential regulatory and antitrust scrutiny"],
            synthesis=synthesis,
            posts=scored_posts,
        )
        return report.to_dict()


# Backward-compatible alias
PulseBlueskyAgent = BlueskyMarketAgent
