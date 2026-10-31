"""GDELT DOC 2.0 Global News Intelligence Agent for Pulse using LangChain.
Queries real-time and historical global news coverage via GDELT DOC 2.0 API,
evaluates macro/corporate sentiment, extracts catalysts, headwinds, and key themes,
and outputs structured JSON reports conforming strictly to the Pulse SignalReport schema.
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
from agents.schemas import SignalReport, PostItem
from agents.gdelt.client import GdeltDocClient

logger = logging.getLogger("GdeltAgent")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@tool
def extract_gdelt_news_tool(topic: str, limit: int = 15) -> str:
    """Query the GDELT DOC 2.0 API for global news coverage, articles, and sentiment regarding any topic or asset."""
    client = GdeltDocClient()
    articles = client.search_articles(query=topic, limit=limit)
    return json.dumps(articles)


class GdeltAgent(BaseAgent):
    """
    LangChain-powered Agent for GDELT DOC 2.0 global news intelligence.
    Produces unified Pulse SignalReport outputs identical in schema to Yahoo Finance and Reddit.
    """

    def __init__(self, output_dir: Optional[str] = None):
        super().__init__(output_dir=output_dir)
        self.client = GdeltDocClient()
        self.tools = [extract_gdelt_news_tool]

    def run(
        self,
        topic: str,
        time_window: str = "day",
        limit: int = 15,
        output_file: Optional[str] = None,
        use_mock: bool = False,
        source_country: Optional[str] = None,
        language: Optional[str] = "English",
    ) -> Dict[str, Any]:
        """
        Execute GDELT DOC 2.0 news collection and sentiment analysis workflow.

        Args:
            topic: Queried asset, company, keyword, or geopolitical topic (e.g. 'NVDA', 'Apple', 'Semiconductors')
            time_window: Time window evaluated ('day', '24h', 'week', 'month')
            limit: Maximum news articles to retrieve and analyze
            output_file: Optional destination path for output JSON
            use_mock: If True, uses synthetic demo data for offline testing
            source_country: Optional source country filter (e.g. 'US', 'GB')
            language: Optional language filter (e.g. 'English')

        Returns:
            Dict containing the structured signal report conforming strictly to SignalReport.
        """
        clean_topic = topic.strip()
        logger.info(
            f"Initiating GDELT DOC 2.0 agent for topic: '{clean_topic}' "
            f"(window: {time_window}, limit={limit}, mock={use_mock})"
        )

        # 1. Query GDELT DOC 2.0 API
        articles = self.client.search_articles(
            query=clean_topic,
            time_window=time_window,
            limit=limit,
            use_mock=use_mock,
            source_country=source_country,
            language=language,
        )

        sources = list(dict.fromkeys(
            a.get("subreddit") or a.get("domain") or "news" for a in articles
        )) or ["gdelt_doc_news"]

        if not articles:
            logger.warning(f"No news articles retrieved from GDELT DOC 2.0 for '{clean_topic}'.")
            empty_report = SignalReport(
                topic=clean_topic,
                time_window=time_window,
                subreddits_scanned=sources,
                total_posts_retrieved=0,
                relevant_posts_count=0,
                aggregate_sentiment_score=0.0,
                sentiment_breakdown={"positive": 0, "neutral": 0, "negative": 0},
                top_themes=[],
                key_positive_catalysts=[],
                key_risk_factors=[],
                synthesis=f"No recent public global news articles indexed by GDELT DOC 2.0 for '{clean_topic}' in the selected time window.",
                posts=[],
            )
            report_dict = empty_report.to_dict()
            self.save_report(report_dict, clean_topic, prefix="gdelt_news", output_file=output_file)
            return report_dict

        # 2. Ingest FinBERT Financial Domain Scoring
        articles = self.score_posts_with_finbert(articles)
        finbert_stats = self.finbert.compute_aggregate(articles) if (self.finbert and self.finbert.is_loaded) else None

        # 3. LangChain Analysis or Heuristic/FinBERT Engine
        if self.llm:
            report_dict = self._process_with_langchain(
                topic=clean_topic,
                articles=articles,
                time_window=time_window,
                sources=sources,
                finbert_stats=finbert_stats,
            )
        else:
            logger.info("Running FinBERT sequence classification scoring engine on GDELT articles.")
            report_dict = self._process_heuristic(
                topic=clean_topic,
                articles=articles,
                time_window=time_window,
                sources=sources,
                finbert_stats=finbert_stats,
            )

        saved_path = self.save_report(report_dict, clean_topic, prefix="gdelt_news", output_file=output_file)
        logger.info(f"GDELT DOC 2.0 signal report successfully saved to: {saved_path}")
        return report_dict

    def _process_with_langchain(
        self,
        topic: str,
        articles: List[Dict[str, Any]],
        time_window: str,
        sources: List[str],
        finbert_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synthesize global news articles, score sentiment, and extract themes using LangChain LLM."""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an institutional financial and geopolitical news intelligence analyst for Pulse, a market signal intelligence platform.
Your task is to analyze news articles retrieved from the GDELT DOC 2.0 global news database regarding the specific topic: '{topic}'.

Guidelines:
1. Relevance Filtering: Disambiguate queries (e.g. verify '{topic}' refers to the intended company, asset, technology, or topic, rather than unrelated entities). Set is_relevant=false if irrelevant.
2. News & Financial Sentiment: Classify each article as "positive", "neutral", or "negative".
   - Assign a sentiment_score from -100.0 (extreme bearish/crisis) to +100.0 (extreme bullish/euphoria).
   - Evaluate macro catalysts, earnings/revenue traction, regulatory/trade policies, capital investments, and competitive positioning.
3. Articles Evaluation: You MUST evaluate every article provided and return it inside the "posts" list with its classification.
4. Synthesis: Provide an executive analytical synthesis of the global media narrative, top catalysts, and market implications.

Output MUST strictly be valid JSON matching this schema:
{{
  "topic": "{topic}",
  "aggregate_sentiment_score": <float between -100.0 and 100.0>,
  "sentiment_breakdown": {{"positive": <int>, "neutral": <int>, "negative": <int>}},
  "top_themes": [<list of top 3-5 themes>],
  "key_positive_catalysts": [<list of 2-3 bullish catalysts with rationale>],
  "key_risk_factors": [<list of 2-3 downside risks or regulatory concerns>],
  "synthesis": "<2-3 paragraph concise executive summary of the global news narrative and sentiment>",
  "posts": [
    {{
      "id": "<article_id>",
      "subreddit": "<domain / news outlet>",
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
      "theme_tags": [<list of strings>],
      "relevance_reason": "<brief rationale>"
    }}
  ]
}}"""),
                ("user", "Topic: {topic}\n\nHere are the raw articles from GDELT DOC 2.0:\n{posts_json}")
            ])

            prepared_posts = []
            for a in articles:
                prepared_posts.append({
                    "id": a.get("id"),
                    "subreddit": a.get("subreddit") or a.get("domain", "news_outlet"),
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "permalink": a.get("permalink") or a.get("url", ""),
                    "published_at": a.get("published_at", ""),
                    "score": a.get("score", 10),
                    "num_comments": 0,
                    "upvote_ratio": 1.0,
                    "content_text": a.get("content_text") or a.get("title", ""),
                    "finbert_score": a.get("finbert_score"),
                    "finbert_label": a.get("finbert_label"),
                })

            posts_json = json.dumps(prepared_posts[:25], indent=2)
            chain = prompt | self.llm | JsonOutputParser()
            result = chain.invoke({
                "topic": topic,
                "posts_json": posts_json,
            })

            # Ensure posts array exists and is well-formed
            if "posts" not in result or not result["posts"]:
                default_label = "positive" if result.get("aggregate_sentiment_score", 0) > 15 else (
                    "negative" if result.get("aggregate_sentiment_score", 0) < -15 else "neutral"
                )
                result["posts"] = [
                    {
                        "id": p.get("id"),
                        "subreddit": p.get("subreddit"),
                        "title": p.get("title"),
                        "url": p.get("url"),
                        "permalink": p.get("permalink"),
                        "published_at": p.get("published_at"),
                        "score": p.get("score", 10),
                        "num_comments": 0,
                        "upvote_ratio": 1.0,
                        "content_text": p.get("content_text"),
                        "is_relevant": True,
                        "sentiment_label": default_label,
                        "confidence": 0.85,
                        "sentiment_score": result.get("aggregate_sentiment_score", 0.0),
                        "theme_tags": result.get("top_themes", ["global_news"]),
                        "relevance_reason": f"Direct news coverage for {topic}"
                    }
                    for p in prepared_posts
                ]

            # Re-attach FinBERT metrics
            art_map = {a.get("id"): a for a in articles}
            for p in result.get("posts", []):
                orig = art_map.get(p.get("id"))
                if orig:
                    p["finbert_label"] = orig.get("finbert_label")
                    p["finbert_score"] = orig.get("finbert_score")
            if finbert_stats:
                result["finbert_aggregate_score"] = finbert_stats.get("aggregate_score")
                result["finbert_breakdown"] = finbert_stats.get("breakdown")
                result["scoring_engine"] = "hybrid (FinBERT + LLM)"

            def _clean_str_list(items: Any) -> List[str]:
                if not isinstance(items, list):
                    return [str(items)] if items else []
                cleaned = []
                for it in items:
                    if isinstance(it, dict):
                        val = (
                            it.get("catalyst")
                            or it.get("risk")
                            or it.get("theme")
                            or it.get("description")
                            or it.get("point")
                            or (list(it.values())[0] if it.values() else str(it))
                        )
                        cleaned.append(str(val))
                    elif it is not None:
                        cleaned.append(str(it))
                return cleaned

            result["top_themes"] = _clean_str_list(result.get("top_themes"))
            result["key_positive_catalysts"] = _clean_str_list(result.get("key_positive_catalysts"))
            result["key_risk_factors"] = _clean_str_list(result.get("key_risk_factors"))

            # Filter out non-relevant articles so report only contains articles truly on-topic
            all_posts = result.get("posts", [])
            relevant_posts = [p for p in all_posts if p.get("is_relevant", True)]
            if relevant_posts:
                result["posts"] = relevant_posts
                pos_c = sum(1 for p in relevant_posts if p.get("sentiment_label") == "positive")
                neg_c = sum(1 for p in relevant_posts if p.get("sentiment_label") == "negative")
                neu_c = sum(1 for p in relevant_posts if p.get("sentiment_label") == "neutral")
                result["sentiment_breakdown"] = {"positive": pos_c, "neutral": neu_c, "negative": neg_c}
                result["aggregate_sentiment_score"] = round(
                    sum(p.get("sentiment_score", 0.0) for p in relevant_posts) / len(relevant_posts), 1
                )

            result["time_window"] = time_window
            result["subreddits_scanned"] = list(dict.fromkeys(p.get("subreddit", "news") for p in result.get("posts", []))) or sources
            result["total_posts_retrieved"] = len(result.get("posts", []))
            result["relevant_posts_count"] = len(result.get("posts", []))
            result["generated_at"] = datetime.now(timezone.utc).isoformat()

            return result

        except Exception as e:
            logger.error(f"LangChain LLM processing failed: {e}. Falling back to heuristic/FinBERT scoring.")
            return self._process_heuristic(topic, articles, time_window, sources, finbert_stats)

    def _process_heuristic(
        self,
        topic: str,
        articles: List[Dict[str, Any]],
        time_window: str,
        sources: List[str],
        finbert_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deterministic scoring fallback utilizing Hugging Face FinBERT or financial keyword rules."""
        bullish_keywords = {
            "surge", "jump", "rally", "gain", "rise", "soar", "beat", "record",
            "upgrade", "bull", "bullish", "growth", "boost", "outperform", "buy",
            "breakthrough", "partnership", "expansion", "profit", "strong"
        }
        bearish_keywords = {
            "fall", "drop", "plunge", "tumble", "slump", "miss", "downgrade",
            "bear", "bearish", "loss", "warning", "sell-off", "decline", "cut",
            "probe", "antitrust", "lawsuit", "investigation", "tariff", "risk"
        }

        processed_posts = []
        pos = 0
        neg = 0
        neu = 0
        total_score = 0.0

        for item in articles:
            content = f"{item.get('title', '')} {item.get('content_text', '')}".lower()
            topic_clean = topic.lower().strip()
            is_relevant = topic_clean in content or len(topic_clean) < 3

            # Prefer FinBERT predictions
            if "finbert_score" in item and item["finbert_score"] is not None:
                score = float(item["finbert_score"])
                label = item.get("finbert_label", "neutral")
                confidence = float(item.get("finbert_confidence", 0.85))
                if label == "positive":
                    pos += 1
                elif label == "negative":
                    neg += 1
                else:
                    neu += 1
            else:
                bull_hits = sum(1 for w in bullish_keywords if w in content)
                bear_hits = sum(1 for w in bearish_keywords if w in content)

                if bull_hits > bear_hits:
                    label = "positive"
                    score = min(25.0 + (bull_hits * 15.0), 90.0)
                    pos += 1
                elif bear_hits > bull_hits:
                    label = "negative"
                    score = max(-25.0 - (bear_hits * 15.0), -90.0)
                    neg += 1
                else:
                    label = "neutral"
                    score = 0.0
                    neu += 1
                confidence = 0.75

            total_score += score
            pub_name = item.get("subreddit") or item.get("domain", "news_outlet")
            link = item.get("url") or item.get("permalink", "")
            title = item.get("title", "")
            body = item.get("content_text") or title

            processed_posts.append({
                "id": item.get("id"),
                "subreddit": pub_name,
                "title": title,
                "url": link,
                "permalink": link,
                "published_at": item.get("published_at", datetime.now(timezone.utc).isoformat()),
                "score": item.get("score", 10),
                "num_comments": 0,
                "upvote_ratio": 1.0,
                "content_text": body,
                "is_relevant": is_relevant,
                "sentiment_label": label,
                "confidence": confidence,
                "sentiment_score": round(score, 1),
                "theme_tags": ["global_news", "market_intelligence"],
                "relevance_reason": f"News coverage matching {topic}",
                "finbert_label": item.get("finbert_label"),
                "finbert_score": item.get("finbert_score"),
                "finbert_confidence": item.get("finbert_confidence"),
            })

        relevant_only = [p for p in processed_posts if p.get("is_relevant", True)]
        final_posts = relevant_only if relevant_only else processed_posts
        count = len(final_posts)
        pos = sum(1 for p in final_posts if p["sentiment_label"] == "positive")
        neg = sum(1 for p in final_posts if p["sentiment_label"] == "negative")
        neu = sum(1 for p in final_posts if p["sentiment_label"] == "neutral")
        avg_score = round(sum(p.get("sentiment_score", 0.0) for p in final_posts) / count, 1) if count > 0 else 0.0

        if avg_score > 15:
            sentiment_summary = f"predominantly positive news tone (+{avg_score})"
        elif avg_score < -15:
            sentiment_summary = f"cautious to negative media sentiment ({avg_score})"
        else:
            sentiment_summary = f"balanced and neutral media coverage ({avg_score})"

        synthesis = (
            f"Global news coverage for '{topic}' indexed by GDELT DOC 2.0 demonstrates {sentiment_summary} "
            f"across {count} analyzed articles from {len(sources)} publishing domains. "
            f"Editorial focus centers on corporate execution, strategic positioning, and sector-wide developments."
        )

        catalysts = [
            f"Constructive coverage on {topic} operational initiatives and capacity expansion across major outlets.",
            f"Broad media attention and institutional commentary highlighting key product milestones.",
        ] if pos > 0 else ["No prominent positive catalysts identified in current news cycle."]

        risks = [
            f"Media scrutiny regarding macroeconomic headwinds, regulatory oversight, or supply constraints.",
            f"Downside volatility highlighted in financial journalism reports.",
        ] if neg > 0 else ["No acute downside risk headlines detected in monitored news batch."]

        themes = ["Global News Coverage", "Corporate Strategy", "Market Narrative"]

        report: Dict[str, Any] = {
            "topic": topic,
            "aggregate_sentiment_score": avg_score,
            "sentiment_breakdown": {"positive": pos, "neutral": neu, "negative": neg},
            "top_themes": themes,
            "key_positive_catalysts": catalysts,
            "key_risk_factors": risks,
            "synthesis": synthesis,
            "posts": final_posts,
            "time_window": time_window,
            "subreddits_scanned": list(dict.fromkeys(p.get("subreddit", "news") for p in final_posts)) or sources,
            "total_posts_retrieved": count,
            "relevant_posts_count": count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scoring_engine": "FinBERT (Hugging Face)" if (self.finbert and self.finbert.is_loaded) else "deterministic heuristic",
        }

        if finbert_stats:
            report["finbert_aggregate_score"] = finbert_stats.get("aggregate_score")
            report["finbert_breakdown"] = finbert_stats.get("breakdown")

        return report


# Backward-compatible aliases
GdeltDocAgent = GdeltAgent
PulseGdeltAgent = GdeltAgent
