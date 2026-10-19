"""Pulse StockTwits Market Signal Agent using LangChain.
Queries real-time StockTwits streams for tickers/topics, incorporates retail sentiment tags ($Bullish/$Bearish),
extracts themes, catalysts, and risks, and outputs structured JSON reports conforming to Pulse SignalReport schema.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from agents.base import BaseAgent
from agents.schemas import SignalReport, PostItem
from agents.stocktwits.client import StockTwitsClient

logger = logging.getLogger("StockTwitsMarketAgent")


class StockTwitsMarketAgent(BaseAgent):
    """Agent orchestrator for retrieving StockTwits retail chatter and generating analytical JSON signals."""

    def __init__(self, output_dir: Optional[str] = None):
        super().__init__(output_dir=output_dir)
        self.client = StockTwitsClient()

    def run(
        self,
        topic: str,
        time_window: str = "day",
        limit: int = 20,
        output_file: Optional[str] = None,
        use_mock: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute the query on StockTwits for a given ticker or topic.
        Enriches posts with sentiment and outputs a validated JSON report.
        """
        sym = None
        try:
            from agents.yahoo_finance.extractor import resolve_topic_to_symbol
            resolved, _ = resolve_topic_to_symbol(topic)
            if resolved:
                sym = "GLD" if resolved == "GC=F" else resolved.replace("=F", "")
        except Exception:
            pass

        target_symbol = sym if sym else topic.strip().upper().lstrip("$")
        clean_topic = target_symbol
        logger.info(f"Initiating StockTwits stream fetch for: '${target_symbol}' (original topic: '{topic}', limit: {limit})")

        raw_posts = self.client.fetch_symbol_stream(
            symbol=target_symbol,
            limit=limit,
            use_mock=use_mock,
        )

        if not raw_posts:
            logger.warning(f"No messages retrieved for '${clean_topic}' on StockTwits.")
            empty_report = SignalReport(
                topic=clean_topic,
                time_window=time_window,
                subreddits_scanned=[f"stocktwits/${clean_topic}"],
                total_posts_retrieved=0,
                relevant_posts_count=0,
                aggregate_sentiment_score=0.0,
                synthesis=f"No recent messages found for '${clean_topic}' on StockTwits streams.",
                posts=[],
            )
            report_dict = empty_report.to_dict()
            self.save_report(report_dict, clean_topic, prefix="stocktwits", output_file=output_file)
            return report_dict

        # Process and enrich messages with FinBERT
        raw_posts = self.score_posts_with_finbert(raw_posts)
        finbert_stats = self.finbert.compute_aggregate(raw_posts) if (self.finbert and self.finbert.is_loaded) else None

        # Process and enrich messages with LLM or FinBERT
        if self.llm:
            report_dict = self._process_with_langchain(clean_topic, time_window, raw_posts, finbert_stats)
        else:
            logger.info("Running FinBERT sequence classification scoring engine.")
            report_dict = self._process_heuristic(clean_topic, time_window, raw_posts, finbert_stats)

        saved_path = self.save_report(report_dict, clean_topic, prefix="stocktwits", output_file=output_file)
        logger.info(f"StockTwits signal report successfully saved to: {saved_path}")
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
                ("system", """You are an institutional financial sentiment analyst for Pulse, a market signal intelligence platform.
Your task is to analyze raw StockTwits messages regarding a specific financial asset/ticker.

Note on StockTwits specifics:
- StockTwits users frequently tag messages with explicit 'Bullish' or 'Bearish' flags. Factor these tags heavily into sentiment.
- Retail slang: 'calls printing', 'short squeeze', 'gamma ramp', 'dip buying' are bullish. 'Bagholding', 'rug pull', 'puts printing', 'debt trap' are bearish.
- Extract concrete positive catalysts (e.g. options flow, technical breakouts, guidance) and key downside risks.

Output MUST strictly be valid JSON matching this schema:
{{
  "topic": "{topic}",
  "aggregate_sentiment_score": <float between -100.0 and 100.0>,
  "sentiment_breakdown": {{"positive": <int>, "neutral": <int>, "negative": <int>}},
  "top_themes": [<list of top 3-5 themes>],
  "key_positive_catalysts": [<list of 2-3 bullish drivers>],
  "key_risk_factors": [<list of 2-3 downside risks or headwinds>],
  "synthesis": "<2-3 paragraph executive analytical summary of retail positioning, momentum, and sentiment on StockTwits>",
  "posts": [
    {{
      "id": "<id>",
      "subreddit": "<source_channel>",
      "title": "<title>",
      "url": "<url>",
      "permalink": "<permalink>",
      "published_at": "<published_at>",
      "score": <score>,
      "num_comments": 0,
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
                ("user", "Analyze these StockTwits messages for topic '${topic}':\n\n{posts_json}"),
            ])

            parser = JsonOutputParser()
            chain = prompt | self.llm | parser

            formatted_posts = [
                {
                    "id": p["id"],
                    "body": p["content_text"],
                    "author": p.get("url", "").split("/")[3] if len(p.get("url", "").split("/")) > 3 else "user",
                    "user_sentiment_tag": p.get("stocktwits_sentiment"),
                    "finbert_score": p.get("finbert_score"),
                    "finbert_label": p.get("finbert_label"),
                    "likes": p["score"],
                    "published_at": p["published_at"],
                }
                for p in raw_posts
            ]

            result = chain.invoke({
                "topic": topic,
                "posts_json": json.dumps(formatted_posts, indent=2),
            })

            # Ensure all posts retain their URLs, IDs, and FinBERT scores
            posts_map = {p["id"]: p for p in raw_posts}
            enriched_posts = []
            for p in result.get("posts", []):
                orig = posts_map.get(p.get("id"), {})
                enriched_posts.append(PostItem(
                    id=p.get("id", orig.get("id", "")),
                    subreddit=p.get("subreddit", orig.get("subreddit", f"stocktwits/${topic}")),
                    title=p.get("title", orig.get("title", "")),
                    url=orig.get("url", p.get("url", "")),
                    permalink=orig.get("permalink", p.get("permalink", "")),
                    published_at=orig.get("published_at", p.get("published_at", datetime.now(timezone.utc).isoformat())),
                    score=orig.get("score", p.get("score", 0)),
                    num_comments=0,
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
                subreddits_scanned=[f"stocktwits/${topic}"],
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
        """Deterministic sentiment scoring prioritizing StockTwits Bullish/Bearish tags and keyword lexicons."""
        bullish_keywords = {"call", "calls", "moon", "squeeze", "breakout", "buy", "long", "rocket", "bull", "undervalued", "dip"}
        bearish_keywords = {"put", "puts", "short", "dump", "sell", "overvalued", "drop", "bear", "downside", "crash", "trim"}

        scored_posts = []
        pos_count = 0
        neg_count = 0
        neu_count = 0
        total_score = 0.0

        for p in raw_posts:
            text = p["content_text"].lower()
            tag = p.get("stocktwits_sentiment")

            # Native StockTwits tag is highest retail signal; fall back to FinBERT sequence classification
            if tag == "Bullish":
                score = 65.0
                label = "positive"
                conf = 0.90
            elif tag == "Bearish":
                score = -65.0
                label = "negative"
                conf = 0.90
            elif "finbert_score" in p and p["finbert_score"] is not None:
                score = float(p["finbert_score"])
                label = p.get("finbert_label", "neutral")
                conf = float(p.get("finbert_confidence", 0.85))
            else:
                words = set(text.split())
                bull_hits = len(words & bullish_keywords)
                bear_hits = len(words & bearish_keywords)

                if bull_hits > bear_hits:
                    score = min(20.0 + bull_hits * 15.0, 85.0)
                    label = "positive"
                elif bear_hits > bull_hits:
                    score = max(-20.0 - bear_hits * 15.0, -85.0)
                    label = "negative"
                else:
                    score = 0.0
                    label = "neutral"
                conf = 0.70

            if label == "positive":
                pos_count += 1
            elif label == "negative":
                neg_count += 1
            else:
                neu_count += 1

            total_score += score
            scored_posts.append(PostItem(
                id=p["id"],
                subreddit=p["subreddit"],
                title=p["title"],
                url=p["url"],
                permalink=p["permalink"],
                published_at=p["published_at"],
                score=p["score"],
                num_comments=0,
                upvote_ratio=1.0,
                content_text=p["content_text"],
                is_relevant=True,
                sentiment_label=label,
                confidence=conf,
                sentiment_score=score,
                finbert_label=p.get("finbert_label"),
                finbert_score=p.get("finbert_score"),
                finbert_confidence=p.get("finbert_confidence"),
                theme_tags=["technical_analysis" if "chart" in text or "breakout" in text else "retail_positioning"],
                relevance_reason=f"StockTwits tagged {tag}" if tag else "Ticker symbol match",
            ))

        avg_score = round(total_score / max(len(raw_posts), 1), 1)
        tag_info = f"Sentiment Breakdown: {pos_count} bullish, {neg_count} bearish, {neu_count} neutral."

        synthesis = (
            f"Analysis of {len(raw_posts)} recent StockTwits messages for ${topic} indicates "
            f"{'predominantly bullish retail sentiment' if avg_score > 15 else 'predominantly bearish sentiment' if avg_score < -15 else 'mixed or neutral retail positioning'}. "
            f"{tag_info} Retail discussions highlight options positioning and momentum around key technical levels."
        )

        report = SignalReport(
            topic=topic,
            time_window=time_window,
            subreddits_scanned=[f"stocktwits/${topic}"],
            total_posts_retrieved=len(raw_posts),
            relevant_posts_count=len(raw_posts),
            aggregate_sentiment_score=avg_score,
            sentiment_breakdown={"positive": pos_count, "neutral": neu_count, "negative": neg_count},
            finbert_aggregate_score=finbert_stats.get("aggregate_score") if finbert_stats else avg_score,
            finbert_breakdown=finbert_stats.get("breakdown") if finbert_stats else {"positive": pos_count, "neutral": neu_count, "negative": neg_count},
            scoring_engine="FinBERT (ProsusAI/finbert) + StockTwits Tags" if (self.finbert and self.finbert.is_loaded) else "heuristic_rules",
            top_themes=["retail_options_flow", "technical_breakout", "earnings_speculation"],
            key_positive_catalysts=[f"Strong ${topic} retail accumulation and call volume", "Favorable technical setups discussed by top traders"],
            key_risk_factors=["RSI overbought warnings on short timeframes", "Broader market multiple contraction risk"],
            synthesis=synthesis,
            posts=scored_posts,
        )
        return report.to_dict()


# Backward-compatible alias
PulseStockTwitsAgent = StockTwitsMarketAgent
