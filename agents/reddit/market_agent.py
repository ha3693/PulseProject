"""Pulse Reddit Market Signal Agent using LangChain.
Queries financial subreddits (r/investing, r/stocks, r/wallstreetbets),
extracts sentiment, themes, and catalysts, and outputs a structured JSON report.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
except ImportError:
    ChatPromptTemplate = None
    JsonOutputParser = None

from agents.base import BaseAgent
from agents.schemas import SignalReport, PostItem
from agents.reddit.client import RedditClient, TARGET_SUBREDDITS

logger = logging.getLogger("RedditMarketAgent")


class RedditMarketAgent(BaseAgent):
    """Agent orchestrator for fetching Reddit news and generating analytical JSON signals."""

    def __init__(self, output_dir: Optional[str] = None):
        super().__init__(output_dir=output_dir)
        self.client = RedditClient()

    def run(
        self,
        topic: str,
        time_window: str = "week",
        limit_per_sub: int = 10,
        output_file: Optional[str] = None,
        use_mock: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute the query across r/investing, r/stocks, and r/wallstreetbets.
        Enriches posts with sentiment and outputs a validated JSON file.
        """
        logger.info(f"Initiating Reddit search for topic: '{topic}' (window: {time_window})")
        raw_posts = self.client.search_subreddits(
            query=topic,
            subreddits=TARGET_SUBREDDITS,
            limit_per_sub=limit_per_sub,
            time_filter=time_window,
            use_mock=use_mock,
        )

        if not raw_posts:
            logger.warning(f"No posts found for topic '{topic}' in target subreddits.")
            empty_report = SignalReport(
                topic=topic,
                time_window=time_window,
                subreddits_scanned=TARGET_SUBREDDITS,
                total_posts_retrieved=0,
                relevant_posts_count=0,
                aggregate_sentiment_score=0.0,
                synthesis=f"No recent public discussions found for '{topic}' across r/investing, r/stocks, or r/wallstreetbets in the selected time window.",
                posts=[],
            )
            report_dict = empty_report.to_dict()
            self.save_report(report_dict, topic, prefix="reddit", output_file=output_file)
            return report_dict

        # Process and enrich posts with FinBERT
        raw_posts = self.score_posts_with_finbert(raw_posts)
        finbert_stats = self.finbert.compute_aggregate(raw_posts) if (self.finbert and self.finbert.is_loaded) else None

        if self.llm:
            report_dict = self._process_with_langchain(topic, time_window, raw_posts, finbert_stats)
        else:
            logger.info("Running FinBERT sequence classification scoring engine.")
            report_dict = self._process_heuristic(topic, time_window, raw_posts, finbert_stats)

        saved_path = self.save_report(report_dict, topic, prefix="reddit", output_file=output_file)
        logger.info(f"Signal report successfully saved to: {saved_path}")
        return report_dict

    def _process_with_langchain(
        self,
        topic: str,
        time_window: str,
        raw_posts: List[Dict[str, Any]],
        finbert_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Use LangChain with structured output/prompt to classify sentiment and synthesize findings."""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert financial sentiment analyst for Pulse, an institutional-grade market signal platform.
Your task is to analyze raw Reddit posts from r/investing, r/stocks, and r/wallstreetbets regarding a specific financial asset/topic.

Guidelines:
1. Relevance Filtering: Disambiguate queries (e.g. verify "Apple" refers to the tech company, not the fruit; "Gold" refers to commodity/currency, not video game currency). If not relevant, set is_relevant=false.
2. Financial Sentiment: Classify each post as "positive", "neutral", or "negative".
   - Assign a sentiment_score from -100.0 (extreme panic/bearish) to +100.0 (extreme euphoria/bullish).
   - Beware of finance slang: "short squeeze", "calls printing", "buying the dip", "diamond hands" are often bullish retail signals. "Bag holding", "dump", "rug pull" are bearish.
3. Themes: Tag key topics (e.g., "earnings", "guidance", "macro", "antitrust", "options_flow").
4. Synthesis: Provide an executive analytical synthesis of what retail investors and commentators are discussing, highlighting key positive drivers and risk factors.

Output MUST strictly be valid JSON matching this schema:
{{
  "topic": "{topic}",
  "aggregate_sentiment_score": <float between -100 and 100>,
  "sentiment_breakdown": {{"positive": <int>, "neutral": <int>, "negative": <int>}},
  "top_themes": [<list of top 3-5 themes>],
  "key_positive_catalysts": [<list of 2-3 bullish points with reasons>],
  "key_risk_factors": [<list of 2-3 bearish points or concerns>],
  "synthesis": "<2-3 paragraph concise executive summary of retail positioning and sentiment>",
  "posts": [
    {{
      "id": "<post_id>",
      "subreddit": "<subreddit>",
      "title": "<title>",
      "url": "<url>",
      "permalink": "<permalink>",
      "published_at": "<published_at>",
      "score": <score>,
      "num_comments": <num_comments>,
      "upvote_ratio": <upvote_ratio>,
      "content_text": "<content_text>",
      "is_relevant": <true/false>,
      "sentiment_label": "<positive|neutral|negative>",
      "confidence": <float between 0.0 and 1.0>,
      "sentiment_score": <float between -100 and 100>,
      "theme_tags": [<strings>],
      "relevance_reason": "<brief reason>"
    }}
  ]
}}"""),
                ("user", "Topic: {topic}\n\nHere are the raw posts retrieved from Reddit:\n{posts_json}")
            ])

            posts_json = json.dumps(raw_posts[:25], indent=2)
            chain = prompt | self.llm | JsonOutputParser()
            result = chain.invoke({"topic": topic, "posts_json": posts_json})

            # Attach FinBERT metrics to each post
            posts_map = {p.get("id"): p for p in raw_posts}
            for p in result.get("posts", []):
                orig = posts_map.get(p.get("id"))
                if orig:
                    p["finbert_label"] = orig.get("finbert_label")
                    p["finbert_score"] = orig.get("finbert_score")
                    p["finbert_confidence"] = orig.get("finbert_confidence")

            if finbert_stats:
                result["finbert_aggregate_score"] = finbert_stats.get("aggregate_score")
                result["finbert_breakdown"] = finbert_stats.get("breakdown")
                result["scoring_engine"] = "hybrid (FinBERT + LLM)"

            # Add metadata
            result["time_window"] = time_window
            result["subreddits_scanned"] = TARGET_SUBREDDITS
            result["total_posts_retrieved"] = len(raw_posts)
            result["relevant_posts_count"] = sum(1 for p in result.get("posts", []) if p.get("is_relevant", True))
            result["generated_at"] = datetime.now(timezone.utc).isoformat()
            return result

        except Exception as e:
            logger.error(f"LangChain processing encountered an error: {e}. Falling back to heuristic scoring.")
            return self._process_heuristic(topic, time_window, raw_posts, finbert_stats)

    def _process_heuristic(
        self,
        topic: str,
        time_window: str,
        raw_posts: List[Dict[str, Any]],
        finbert_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deterministic scoring fallback utilizing Hugging Face FinBERT or keyword rules."""
        bullish_words = {"call", "calls", "buy", "bull", "bullish", "moon", "squeeze", "beat", "surge", "growth", "breakout"}
        bearish_words = {"put", "puts", "sell", "bear", "bearish", "crash", "drop", "dump", "overvalued", "loss", "plummet"}

        processed_posts = []
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
                text = f"{p['title']} {p['content_text']}".lower()
                bull_score = sum(1 for w in bullish_words if w in text)
                bear_score = sum(1 for w in bearish_words if w in text)

                if bull_score > bear_score:
                    label = "positive"
                    score = min(25.0 + (bull_score * 15.0), 90.0)
                    pos_count += 1
                elif bear_score > bull_score:
                    label = "negative"
                    score = max(-25.0 - (bear_score * 15.0), -90.0)
                    neg_count += 1
                else:
                    label = "neutral"
                    score = 0.0
                    neu_count += 1
                confidence = 0.75

            total_score += score
            processed_posts.append({
                **p,
                "is_relevant": True,
                "sentiment_label": label,
                "confidence": confidence,
                "sentiment_score": round(score, 2),
                "theme_tags": ["retail_discussion", "market_action"],
                "relevance_reason": f"Direct mention of query '{topic}'",
            })

        avg_score = round(total_score / len(processed_posts), 2) if processed_posts else 0.0

        return {
            "topic": topic,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "time_window": time_window,
            "subreddits_scanned": TARGET_SUBREDDITS,
            "total_posts_retrieved": len(raw_posts),
            "relevant_posts_count": len(processed_posts),
            "aggregate_sentiment_score": avg_score,
            "sentiment_breakdown": {
                "positive": pos_count,
                "neutral": neu_count,
                "negative": neg_count,
            },
            "finbert_aggregate_score": finbert_stats.get("aggregate_score") if finbert_stats else avg_score,
            "finbert_breakdown": finbert_stats.get("breakdown") if finbert_stats else {"positive": pos_count, "neutral": neu_count, "negative": neg_count},
            "scoring_engine": "FinBERT (ProsusAI/finbert)" if (self.finbert and self.finbert.is_loaded) else "heuristic_rules",
            "top_themes": ["retail_sentiment", "options_speculation", "earnings"],
            "key_positive_catalysts": [f"Bullish mentions across r/{p['subreddit']}" for p in processed_posts if p["sentiment_label"] == "positive"][:3],
            "key_risk_factors": [f"Bearish concerns noted in r/{p['subreddit']}" for p in processed_posts if p["sentiment_label"] == "negative"][:3],
            "synthesis": f"Analysis of {len(processed_posts)} recent Reddit discussions across r/investing, r/stocks, and r/wallstreetbets regarding '{topic}'. Overall weighted sentiment index is {avg_score} (-100 to +100).",
            "posts": processed_posts,
        }


# Alias for backward compatibility
PulseRedditAgent = RedditMarketAgent
