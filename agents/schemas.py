"""Unified Pydantic data schemas for Pulse Agents.
Defines standard signal reports, post items, and market context models.
Maintains full backward-compatibility with all existing agent consumers.
"""

from datetime import datetime, timezone
from typing import List, Optional, Literal, Dict, Any

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self):
            return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
    def Field(default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default


class EODMarketContext(BaseModel):
    """End-of-day market quote and price action context for the underlying asset."""
    symbol: str = Field(description="Ticker symbol (e.g. 'NVDA', 'GC=F', 'NKE')")
    name: Optional[str] = Field(default=None, description="Company or asset short name")
    last_price: Optional[float] = Field(default=None, description="Latest or closing market price")
    previous_close: Optional[float] = Field(default=None, description="Previous session closing price")
    change: Optional[float] = Field(default=None, description="Net price change in currency units")
    change_percent: Optional[float] = Field(default=None, description="Percentage change in price")
    day_high: Optional[float] = Field(default=None, description="Intraday high price")
    day_low: Optional[float] = Field(default=None, description="Intraday low price")
    volume: Optional[int] = Field(default=None, description="Trading volume")
    currency: Optional[str] = Field(default="USD", description="Currency denominator")
    market_state: Optional[str] = Field(default="CLOSED", description="Market session state (CLOSED, REGULAR, PRE, POST)")
    as_of: Optional[str] = Field(default=None, description="Timestamp of market quote")


class PostItem(BaseModel):
    """
    Standardized schema for an individual post or news article ingested by any Pulse agent.
    Compatible across Reddit (market/user) and Yahoo Finance EOD feeds.
    """
    id: str = Field(description="Unique source post or article identifier")
    subreddit: str = Field(description="Subreddit or publishing outlet name (e.g. 'investing', 'Bloomberg')")
    title: str = Field(description="Title or headline")
    url: str = Field(description="Direct link to the post or external article")
    permalink: str = Field(description="Canonical path or URL")
    published_at: str = Field(description="ISO 8601 publication timestamp")
    score: int = Field(default=0, description="Upvote score or engagement count")
    num_comments: int = Field(default=0, description="Total comment count")
    upvote_ratio: float = Field(default=1.0, description="Ratio of upvotes (0.0 to 1.0)")
    content_text: str = Field(description="Cleaned post selftext, snippet, or summary")
    is_relevant: bool = Field(default=True, description="Whether item directly pertains to the queried topic/asset")
    sentiment_label: Literal["positive", "neutral", "negative"] = Field(
        default="neutral",
        description="Sentiment classification: positive, neutral, or negative"
    )
    confidence: float = Field(default=0.75, ge=0.0, le=1.0, description="Confidence score 0.0 to 1.0")
    sentiment_score: float = Field(
        default=0.0,
        ge=-100.0,
        le=100.0,
        description="Normalized sentiment score between -100 (extreme bearish) and +100 (extreme bullish)"
    )
    theme_tags: List[str] = Field(
        default_factory=list,
        description="Theme tags (e.g. ['earnings', 'guidance', 'ai_hardware', 'options_flow'])"
    )
    relevance_reason: Optional[str] = Field(default=None, description="Brief rationale for inclusion or filtering")
    finbert_label: Optional[Literal["positive", "neutral", "negative"]] = Field(
        default=None,
        description="FinBERT classification: positive, neutral, or negative"
    )
    finbert_score: Optional[float] = Field(
        default=None,
        description="FinBERT net score between -100.0 (bearish) and +100.0 (bullish)"
    )
    finbert_confidence: Optional[float] = Field(
        default=None,
        description="FinBERT model confidence (0.0 to 1.0)"
    )


class SignalReport(BaseModel):
    """
    Unified output report schema saved as JSON for the Pulse application.
    Produced by Reddit Market Agent, Yahoo Finance EOD Agent, and other data sources.
    """
    topic: str = Field(description="Queried topic or ticker symbol (e.g. 'NVDA', 'AAPL', 'Gold', 'Nike')")
    aggregate_sentiment_score: float = Field(
        default=0.0,
        ge=-100.0,
        le=100.0,
        description="Weighted sentiment index (-100 = extremely bearish, +100 = extremely bullish)"
    )
    sentiment_breakdown: Dict[str, int] = Field(
        default_factory=lambda: {"positive": 0, "neutral": 0, "negative": 0}
    )
    top_themes: List[str] = Field(default_factory=list, description="Top 3-5 themes identified across items")
    key_positive_catalysts: List[str] = Field(default_factory=list, description="Top positive catalysts or bullish points")
    key_risk_factors: List[str] = Field(default_factory=list, description="Key headwinds or downside risks")
    synthesis: str = Field(description="Executive analytical summary of public discourse and sentiment")
    posts: List[PostItem] = Field(default_factory=list, description="List of analyzed post items")
    time_window: str = Field(default="week", description="Time window evaluated: '24h', 'day', 'week', or 'month'")
    subreddits_scanned: List[str] = Field(
        default_factory=list,
        description="Channels, subreddits, or news sources scanned"
    )
    total_posts_retrieved: int = Field(default=0, description="Total raw posts ingested")
    relevant_posts_count: int = Field(default=0, description="Number of posts confirmed relevant to topic")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # FinBERT Domain Scoring Benchmark & Calibration
    finbert_aggregate_score: Optional[float] = Field(
        default=None,
        description="Aggregate sentiment score derived directly from HuggingFace FinBERT model"
    )
    finbert_breakdown: Optional[Dict[str, int]] = Field(
        default=None,
        description="Sentiment distribution determined by FinBERT model"
    )
    scoring_engine: Optional[str] = Field(
        default="hybrid (FinBERT + LLM)",
        description="NLP model pipeline used for scoring (e.g. 'FinBERT', 'LLM', or 'hybrid')"
    )

    # Optional complementary market pricing data
    market_context: Optional[EODMarketContext] = Field(default=None, description="EOD closing market metrics")
    resolved_symbol: Optional[str] = Field(default=None, description="Resolved Yahoo Finance symbol (e.g. 'NVDA', 'GC=F', 'NKE')")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.__dict__


# Backward compatibility aliases
RedditPostItem = PostItem
YahooNewsItem = PostItem
RedditSignalReport = SignalReport
YahooFinanceSignalReport = SignalReport
