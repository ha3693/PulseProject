"""Pydantic data schemas for Reddit sentiment and market signals."""

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


class RedditPostItem(BaseModel):
    """Schema for an individual Reddit post ingested and processed by Pulse."""
    id: str = Field(description="Unique Reddit post ID (e.g., '1h3jk9')")
    subreddit: str = Field(description="Subreddit source (e.g., 'investing', 'stocks', 'wallstreetbets')")
    title: str = Field(description="Title of the Reddit submission")
    url: str = Field(description="Direct link to the post or external link")
    permalink: str = Field(description="Reddit permalink path")
    published_at: str = Field(description="ISO 8601 publication timestamp")
    score: int = Field(default=0, description="Upvote score")
    num_comments: int = Field(default=0, description="Total comment count")
    upvote_ratio: float = Field(default=1.0, description="Ratio of upvotes (0.0 to 1.0)")
    content_text: str = Field(description="Cleaned post selftext or excerpt")
    is_relevant: bool = Field(default=True, description="Whether post directly pertains to the financial topic/asset")
    sentiment_label: Literal["positive", "neutral", "negative"] = Field(
        default="neutral", 
        description="Sentiment classification"
    )
    confidence: float = Field(default=0.7, ge=0.0, le=1.0, description="Confidence score 0.0 to 1.0")
    sentiment_score: float = Field(
        default=0.0, 
        ge=-100.0, 
        le=100.0, 
        description="Normalized sentiment index score between -100 and +100"
    )
    theme_tags: List[str] = Field(
        default_factory=list, 
        description="Theme tags (e.g. ['earnings', 'guidance', 'ai_chips', 'options_flow'])"
    )
    relevance_reason: Optional[str] = Field(default=None, description="Brief rationale for inclusion or filtering")


class RedditSignalReport(BaseModel):
    """Aggregated output report saved as JSON for the Pulse application."""
    topic: str = Field(description="Queried topic or ticker symbol (e.g. 'NVDA', 'AAPL', 'Gold')")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    time_window: str = Field(default="week", description="Time window evaluated: '24h', 'week', or 'month'")
    subreddits_scanned: List[str] = Field(default_factory=lambda: ["investing", "stocks", "wallstreetbets"])
    total_posts_retrieved: int = Field(default=0)
    relevant_posts_count: int = Field(default=0)
    aggregate_sentiment_score: float = Field(
        default=0.0, 
        ge=-100.0, 
        le=100.0, 
        description="Weighted sentiment index (-100 = extremely bearish/negative, +100 = extremely bullish/positive)"
    )
    sentiment_breakdown: Dict[str, int] = Field(
        default_factory=lambda: {"positive": 0, "neutral": 0, "negative": 0}
    )
    top_themes: List[str] = Field(default_factory=list)
    key_positive_catalysts: List[str] = Field(default_factory=list)
    key_risk_factors: List[str] = Field(default_factory=list)
    synthesis: str = Field(description="Executive analytical summary of retail sentiment and public discourse")
    posts: List[RedditPostItem] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
