"""Yahoo Finance End-of-Day (EOD) Market & News Agent powered by LangChain."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from agents.base import BaseAgent
from agents.schemas import SignalReport, PostItem, EODMarketContext
from agents.yahoo_finance.extractor import (
    fetch_yahoo_finance_news,
    fetch_eod_market_data,
    resolve_topic_to_symbol
)

logger = logging.getLogger("YahooFinanceAgent")


@tool
def extract_yahoo_eod_news_tool(topic: str, limit: int = 10) -> str:
    """Fetch Yahoo Finance news and End-of-Day market quotes for any topic, asset ticker, or commodity."""
    res = fetch_yahoo_finance_news(topic=topic, limit=limit)
    return json.dumps(res)


@tool
def get_eod_market_quote_tool(symbol: str) -> str:
    """Retrieve End-of-Day (EOD) market metrics for a specific ticker symbol (e.g. 'NVDA', 'GC=F', 'NKE')."""
    res = fetch_eod_market_data(symbol)
    return json.dumps(res or {})


class YahooFinanceAgent(BaseAgent):
    """
    LangChain-powered Agent for Yahoo Finance End-of-Day news.
    Outputs the identical JSON schema as RedditSignalReport for the main Pulse application.
    """

    def __init__(self, output_dir: Optional[str] = None):
        super().__init__(output_dir=output_dir)
        self.tools = [extract_yahoo_eod_news_tool, get_eod_market_quote_tool]

    def run(
        self,
        topic: str,
        time_window: str = "day",
        limit: int = 10,
        output_file: Optional[str] = None,
        use_mock: bool = False
    ) -> Dict[str, Any]:
        """
        Execute Yahoo Finance EOD news query and generate structured JSON report identical to Reddit.

        Args:
            topic: User input topic (e.g. 'NVDA', 'Gold', 'Nike')
            time_window: Time window evaluated ('day', '24h', 'week', 'month')
            limit: Maximum news articles to retrieve and analyze
            output_file: Optional destination path for output JSON
            use_mock: If True, uses synthetic demo data for offline execution

        Returns:
            Dict containing the structured signal report matching SignalReport.
        """
        clean_topic = topic.strip()
        logger.info(f"Initiating Yahoo Finance EOD agent for topic: '{clean_topic}' (window: {time_window}, limit={limit})")

        # Step 1: Ingest Yahoo Finance EOD feed & market snapshot
        feed = fetch_yahoo_finance_news(
            topic=clean_topic,
            limit=limit,
            use_mock=use_mock,
            enrich_snippets=True
        )

        news_items = feed.get("news_items", [])
        market_data = feed.get("market_data")
        symbol = feed.get("symbol")
        asset_name = feed.get("asset_name", clean_topic)

        sources = list(dict.fromkeys(
            p.get("subreddit") or p.get("publisher") or "yahoo_finance" for p in news_items
        )) or ["yahoo_finance", "financial_news"]

        if not news_items:
            logger.warning(f"No news items retrieved from Yahoo Finance for '{clean_topic}'.")
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
                synthesis=f"No recent public financial news found on Yahoo Finance for '{clean_topic}' in the selected time window.",
                posts=[],
                market_context=EODMarketContext(**market_data) if market_data else None,
                resolved_symbol=symbol
            )
            out_dict = empty_report.to_dict()
            self.save_report(out_dict, clean_topic, prefix="yahoo_news", output_file=output_file)
            return out_dict

        # Step 2: LangChain Analysis or Heuristic Engine
        if self.llm:
            report_dict = self._process_with_langchain(
                topic=clean_topic,
                symbol=symbol,
                asset_name=asset_name,
                market_data=market_data,
                news_items=news_items,
                time_window=time_window,
                sources=sources
            )
        else:
            logger.info("Running deterministic heuristic scoring engine.")
            report_dict = self._process_heuristic(
                topic=clean_topic,
                symbol=symbol,
                asset_name=asset_name,
                market_data=market_data,
                news_items=news_items,
                time_window=time_window,
                sources=sources
            )

        saved_path = self.save_report(report_dict, clean_topic, prefix="yahoo_news", output_file=output_file)
        logger.info(f"Signal report successfully saved to: {saved_path}")
        return report_dict

    def _process_with_langchain(
        self,
        topic: str,
        symbol: Optional[str],
        asset_name: str,
        market_data: Optional[Dict[str, Any]],
        news_items: List[Dict[str, Any]],
        time_window: str,
        sources: List[str]
    ) -> Dict[str, Any]:
        """Synthesize headlines, score financial sentiment, and generate report matching Reddit JSON schema."""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert financial sentiment and market signal analyst for Pulse, an institutional-grade market intelligence platform.
Your task is to analyze End-of-Day (EOD) Yahoo Finance news articles regarding a specific financial asset/topic: '{topic}' (Asset: {asset_name}, Symbol: {symbol}).

Market Context:
{market_context_str}

Guidelines:
1. Relevance Filtering: Disambiguate queries (e.g. verify 'Gold' refers to gold commodity/bullion/miners, not unrelated healthcare cards or games; 'Nike' refers to footwear/apparel/retail). If not relevant, set is_relevant=false.
2. Financial Sentiment: Classify each post as "positive", "neutral", or "negative".
   - Assign a sentiment_score from -100.0 (extreme panic/bearish) to +100.0 (extreme euphoria/bullish).
   - Evaluate institutional catalysts: earnings, guidance, price targets, capex, supply chain, regulatory probes.
3. Posts Evaluation: You MUST evaluate every post in the input and return it inside the "posts" list with its classification.
4. Synthesis: Provide an executive analytical synthesis of the news cycle, market narrative, and how news correlates with EOD price performance.

Output MUST strictly be valid JSON matching this schema:
{{
  "topic": "{topic}",
  "aggregate_sentiment_score": <float between -100 and 100>,
  "sentiment_breakdown": {{"positive": <int>, "neutral": <int>, "negative": <int>}},
  "top_themes": [<list of top 3-5 themes>],
  "key_positive_catalysts": [<list of 2-3 bullish points with reasons>],
  "key_risk_factors": [<list of 2-3 bearish points or concerns>],
  "synthesis": "<2-3 paragraph concise executive summary of market narrative and sentiment>",
  "posts": [
    {{
      "id": "<post_id>",
      "subreddit": "<publisher / outlet name>",
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
                ("user", "Topic: {topic}\n\nHere are the raw articles retrieved from Yahoo Finance:\n{posts_json}")
            ])

            market_context_str = json.dumps(market_data, indent=2) if market_data else "No live price quote available."

            prepared_posts = []
            for p in news_items:
                prepared_posts.append({
                    "id": p.get("id"),
                    "subreddit": p.get("subreddit") or p.get("publisher", "Yahoo Finance"),
                    "title": p.get("title", ""),
                    "url": p.get("url") or p.get("link", ""),
                    "permalink": p.get("permalink") or p.get("link", ""),
                    "published_at": p.get("published_at", ""),
                    "score": p.get("score", 0),
                    "num_comments": p.get("num_comments", 0),
                    "upvote_ratio": p.get("upvote_ratio", 1.0),
                    "content_text": p.get("content_text") or p.get("summary") or p.get("title", ""),
                    "time_ago": p.get("time_ago", "recently")
                })

            posts_json = json.dumps(prepared_posts[:25], indent=2)
            chain = prompt | self.llm | JsonOutputParser()
            result = chain.invoke({
                "topic": topic,
                "symbol": symbol or topic,
                "asset_name": asset_name,
                "market_context_str": market_context_str,
                "posts_json": posts_json,
            })

            # Ensure posts array is guaranteed to be present and structured
            if "posts" not in result or not result["posts"]:
                default_label = "positive" if result.get("aggregate_sentiment_score", 0) > 15 else ("negative" if result.get("aggregate_sentiment_score", 0) < -15 else "neutral")
                result["posts"] = [
                    {
                        "id": p.get("id"),
                        "subreddit": p.get("subreddit"),
                        "title": p.get("title"),
                        "url": p.get("url"),
                        "permalink": p.get("permalink"),
                        "published_at": p.get("published_at"),
                        "score": p.get("score", 0),
                        "num_comments": p.get("num_comments", 0),
                        "upvote_ratio": p.get("upvote_ratio", 1.0),
                        "content_text": p.get("content_text"),
                        "is_relevant": True,
                        "sentiment_label": default_label,
                        "confidence": 0.85,
                        "sentiment_score": result.get("aggregate_sentiment_score", 0.0),
                        "theme_tags": result.get("top_themes", ["market_news"]),
                        "relevance_reason": f"Direct financial coverage for {topic}"
                    }
                    for p in prepared_posts
                ]

            # Add operational metadata matching SignalReport exactly
            result["time_window"] = time_window
            result["subreddits_scanned"] = sources
            result["total_posts_retrieved"] = len(news_items)
            result["relevant_posts_count"] = sum(1 for p in result.get("posts", []) if p.get("is_relevant", True))
            result["generated_at"] = datetime.now(timezone.utc).isoformat()
            if market_data:
                result["market_context"] = market_data
            if symbol:
                result["resolved_symbol"] = symbol

            return result

        except Exception as e:
            logger.error(f"LangChain LLM processing encountered error: {e}. Falling back to heuristic scoring.")
            return self._process_heuristic(topic, symbol, asset_name, market_data, news_items, time_window, sources)

    def _process_heuristic(
        self,
        topic: str,
        symbol: Optional[str],
        asset_name: str,
        market_data: Optional[Dict[str, Any]],
        news_items: List[Dict[str, Any]],
        time_window: str,
        sources: List[str]
    ) -> Dict[str, Any]:
        """Deterministic heuristic fallback scoring when no LLM key is configured."""
        bullish_keywords = {
            "surge", "jump", "rally", "gain", "rise", "soar", "beat", "record",
            "upgrade", "bull", "bullish", "growth", "boost", "outperform", "buy", "top pick"
        }
        bearish_keywords = {
            "fall", "drop", "plunge", "tumble", "slump", "miss", "downgrade",
            "bear", "bearish", "loss", "warning", "sell-off", "decline", "cut", "probe", "antitrust"
        }

        processed_posts = []
        pos = 0
        neg = 0
        neu = 0
        total_score = 0.0

        for item in news_items:
            content = f"{item.get('title', '')} {item.get('content_text', '')}".lower()
            bull_hits = sum(1 for w in bullish_keywords if w in content)
            bear_hits = sum(1 for w in bearish_keywords if w in content)

            topic_terms = [topic.lower(), (symbol or "").lower(), asset_name.lower().split()[0]]
            is_relevant = any(term in content for term in topic_terms if len(term) >= 3)
            if not is_relevant:
                is_relevant = True

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

            total_score += score
            pub_name = item.get("subreddit") or item.get("publisher", "Yahoo Finance")
            link = item.get("url") or item.get("link", "")
            title = item.get("title", "")
            body = item.get("content_text") or item.get("summary") or title

            processed_posts.append({
                "id": item.get("id", str(hash(link))),
                "subreddit": pub_name,
                "title": title,
                "url": link,
                "permalink": link,
                "published_at": item.get("published_at", datetime.now(timezone.utc).isoformat()),
                "score": item.get("score", 0),
                "num_comments": item.get("num_comments", 0),
                "upvote_ratio": item.get("upvote_ratio", 1.0),
                "content_text": body,
                "is_relevant": is_relevant,
                "sentiment_label": label,
                "confidence": 0.75,
                "sentiment_score": round(score, 2),
                "theme_tags": ["market_news", "eod_feed"],
                "relevance_reason": f"Mention of query '{topic}'",
            })

        avg_score = round(total_score / len(processed_posts), 2) if processed_posts else 0.0

        price_str = ""
        if market_data and market_data.get("last_price") is not None:
            lp = market_data.get("last_price")
            chg = market_data.get("change", 0.0)
            chg_pct = market_data.get("change_percent", 0.0)
            sign = "+" if chg >= 0 else ""
            price_str = f" {asset_name} closed the session at ${lp:,.2f} ({sign}{chg:.2f}, {sign}{chg_pct:.2f}%)."

        return {
            "topic": topic,
            "aggregate_sentiment_score": avg_score,
            "sentiment_breakdown": {"positive": pos, "neutral": neu, "negative": neg},
            "top_themes": ["market_sentiment", "eod_performance", "analyst_coverage"],
            "key_positive_catalysts": [
                f"Constructive coverage in {p['subreddit']}: {p['title']}"
                for p in processed_posts if p["sentiment_label"] == "positive"
            ][:3],
            "key_risk_factors": [
                f"Headwinds reported in {p['subreddit']}: {p['title']}"
                for p in processed_posts if p["sentiment_label"] == "negative"
            ][:3],
            "synthesis": (
                f"Analysis of {len(processed_posts)} recent Yahoo Finance headlines regarding '{topic}' ({asset_name}). "
                f"Overall composite sentiment index is {avg_score} (-100 to +100).{price_str}"
            ),
            "posts": processed_posts,
            "time_window": time_window,
            "subreddits_scanned": sources,
            "total_posts_retrieved": len(news_items),
            "relevant_posts_count": len(processed_posts),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "market_context": market_data,
            "resolved_symbol": symbol
        }
