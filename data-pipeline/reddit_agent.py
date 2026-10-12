#!/usr/bin/env python3
"""
Pulse Platform - Reddit Market Signal Agent using LangChain
Queries financial subreddits (r/investing, r/stocks, r/wallstreetbets),
extracts sentiment, themes, and catalysts, and outputs a structured JSON report.
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Load local environment variables from root or local .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    root_env = Path(__file__).resolve().parent.parent / ".env"
    local_env = Path(__file__).resolve().parent / ".env"
    if root_env.exists():
        load_dotenv(root_env)
    elif local_env.exists():
        load_dotenv(local_env)
    else:
        load_dotenv()
except ImportError:
    pass

# Add parent directory to sys.path to allow imports from src
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from src.schemas import RedditPostItem, RedditSignalReport
from src.reddit_client import RedditClient, TARGET_SUBREDDITS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PulseRedditAgent")


def get_llm():
    """Instantiate the preferred Chat model based on available environment keys."""
    # 1. Google Gemini
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                temperature=0.2,
                google_api_key=api_key,
            )
        except ImportError:
            logger.warning("langchain-google-genai not installed.")

    # 2. OpenAI
    if os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.2,
                api_key=os.getenv("OPENAI_API_KEY"),
            )
        except ImportError:
            logger.warning("langchain-openai not installed.")

    # 3. Anthropic Claude
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model="claude-3-5-sonnet-20240620",
                temperature=0.2,
                api_key=os.getenv("ANTHROPIC_API_KEY"),
            )
        except ImportError:
            logger.warning("langchain-anthropic not installed.")

    return None


class PulseRedditAgent:
    """Agent orchestrator for fetching Reddit news and generating analytical JSON signals."""

    def __init__(self, output_dir: Optional[str] = None):
        self.client = RedditClient()
        self.output_dir = Path(output_dir) if output_dir else Path(__file__).resolve().parent / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.llm = get_llm()

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
            empty_report = RedditSignalReport(
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
            self._save_report(report_dict, topic, output_file)
            return report_dict

        # Process and enrich posts
        if self.llm:
            report_dict = self._process_with_langchain(topic, time_window, raw_posts)
        else:
            logger.info("No LLM API key detected or LangChain package missing. Running heuristic sentiment engine.")
            report_dict = self._process_heuristic(topic, time_window, raw_posts)

        saved_path = self._save_report(report_dict, topic, output_file)
        logger.info(f"Signal report successfully saved to: {saved_path}")
        return report_dict

    def _process_with_langchain(
        self,
        topic: str,
        time_window: str,
        raw_posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Use LangChain with structured output/prompt to classify sentiment and synthesize findings."""
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import JsonOutputParser

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

            # Prepare posts payload
            posts_json = json.dumps(raw_posts[:25], indent=2)
            chain = prompt | self.llm | JsonOutputParser()
            result = chain.invoke({"topic": topic, "posts_json": posts_json})

            # Add metadata
            result["time_window"] = time_window
            result["subreddits_scanned"] = TARGET_SUBREDDITS
            result["total_posts_retrieved"] = len(raw_posts)
            result["relevant_posts_count"] = sum(1 for p in result.get("posts", []) if p.get("is_relevant", True))
            result["generated_at"] = datetime.now(timezone.utc).isoformat()
            return result

        except Exception as e:
            logger.error(f"LangChain processing encountered an error: {e}. Falling back to heuristic scoring.")
            return self._process_heuristic(topic, time_window, raw_posts)

    def _process_heuristic(
        self,
        topic: str,
        time_window: str,
        raw_posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Deterministic heuristic fallback scoring when no LLM key is configured."""
        bullish_words = {"call", "calls", "buy", "bull", "bullish", "moon", "squeeze", "beat", "surge", "growth", "breakout"}
        bearish_words = {"put", "puts", "sell", "bear", "bearish", "crash", "drop", "dump", "overvalued", "loss", "plummet"}

        processed_posts = []
        pos_count = 0
        neg_count = 0
        neu_count = 0
        total_score = 0.0

        for p in raw_posts:
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

            total_score += score
            processed_posts.append({
                **p,
                "is_relevant": True,
                "sentiment_label": label,
                "confidence": 0.75,
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
            "top_themes": ["retail_sentiment", "options_speculation", "earnings"],
            "key_positive_catalysts": [f"Bullish mentions across r/{p['subreddit']}" for p in processed_posts if p["sentiment_label"] == "positive"][:3],
            "key_risk_factors": [f"Bearish concerns noted in r/{p['subreddit']}" for p in processed_posts if p["sentiment_label"] == "negative"][:3],
            "synthesis": f"Analysis of {len(processed_posts)} recent Reddit discussions across r/investing, r/stocks, and r/wallstreetbets regarding '{topic}'. Overall weighted sentiment index is {avg_score} (-100 to +100).",
            "posts": processed_posts,
        }

    def _save_report(
        self,
        report_data: Dict[str, Any],
        topic: str,
        output_file: Optional[str] = None
    ) -> Path:
        """Serialize data to JSON file."""
        if output_file:
            path = Path(output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            safe_topic = "".join(c if c.isalnum() else "_" for c in topic.lower())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self.output_dir / f"reddit_{safe_topic}_{timestamp}.json"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        return path


def main():
    parser = argparse.ArgumentParser(
        description="Pulse Reddit Market Signal Agent - Query r/investing, r/stocks, r/wallstreetbets"
    )
    parser.add_argument(
        "--topic",
        "-t",
        type=str,
        default="NVDA",
        help="Topic, asset ticker, or brand to query (e.g. 'NVDA', 'AAPL', 'Gold', 'Nike')"
    )
    parser.add_argument(
        "--window",
        "-w",
        type=str,
        default="week",
        choices=["24h", "day", "7d", "week", "month"],
        help="Time window for search ('24h', 'week', 'month')"
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=8,
        help="Maximum posts to retrieve per subreddit (default: 8)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional destination path for the JSON output file"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run using representative synthetic data (useful for offline testing or demo)"
    )

    args = parser.parse_args()

    agent = PulseRedditAgent()
    result = agent.run(
        topic=args.topic,
        time_window=args.window,
        limit_per_sub=args.limit,
        output_file=args.output,
        use_mock=args.mock,
    )

    print("\n" + "=" * 60)
    print(f"📊 Pulse Reddit Signal Report for: {result.get('topic')}")
    print(f"Index Score: {result.get('aggregate_sentiment_score')} (-100 to +100)")
    print(f"Breakdown: {result.get('sentiment_breakdown')}")
    print(f"Posts Scanned: {result.get('total_posts_retrieved')} | Relevant: {result.get('relevant_posts_count')}")
    print("=" * 60)
    print(f"Synthesis:\n{result.get('synthesis')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
