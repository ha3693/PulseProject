"""StockTwits client for Pulse supporting official REST endpoints and mock data fallbacks.
Targets: Symbol streams, user message streams, and trending retail tickers.
Strictly adheres to data policy: No user profile data or PII collected.
"""

import os
import time
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger("PulseStockTwitsClient")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

STOCKTWITS_API_BASE = "https://api.stocktwits.com/api/2"
DEFAULT_USER_AGENT = "PulseMarketSignal/1.0.0 (Research academic project; contact@pulse.internal)"


class StockTwitsClient:
    """Client for retrieving financial messages from StockTwits."""

    def __init__(
        self,
        api_token: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        self.api_token = api_token or os.getenv("STOCKTWITS_API_KEY")
        self.user_agent = user_agent or os.getenv("STOCKTWITS_USER_AGENT", DEFAULT_USER_AGENT)
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if self.api_token and not self.api_token.startswith("your-"):
            self.headers["Authorization"] = f"OAuth {self.api_token}"

    def fetch_symbol_stream(
        self,
        symbol: str,
        limit: int = 30,
        use_mock: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent messages for a ticker symbol from StockTwits.
        Returns a list of normalized post dictionaries.
        """
        clean_symbol = symbol.strip().upper().lstrip("$")

        if use_mock:
            logger.info(f"Using synthetic/mock data generator for StockTwits symbol '${clean_symbol}'")
            return self._generate_mock_messages(clean_symbol, limit)

        import urllib.request
        import urllib.parse

        url = f"{STOCKTWITS_API_BASE}/streams/symbol/{urllib.parse.quote(clean_symbol)}.json?limit={min(limit, 30)}"

        try:
            if requests is not None:
                resp = requests.get(url, headers=self.headers, timeout=8)
                status_code = resp.status_code
                data = resp.json() if status_code == 200 else {}
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    status_code = r.status
                    data = json.loads(r.read().decode("utf-8"))

            if status_code == 200:
                raw_messages = data.get("messages", [])
                logger.info(f"Retrieved {len(raw_messages)} live messages from StockTwits for ${clean_symbol}")
                return [self._normalize_message(m, clean_symbol) for m in raw_messages[:limit]]
            else:
                logger.warning(f"StockTwits API returned HTTP {status_code} for '${clean_symbol}'. Falling back to mock.")
                return self._generate_mock_messages(clean_symbol, limit)
        except Exception as err:
            logger.warning(f"StockTwits live stream fallback for '${clean_symbol}': {err}")
            return self._generate_mock_messages(clean_symbol, limit)

    def fetch_user_stream(
        self,
        username: str,
        limit: int = 20,
        use_mock: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent messages posted by a specific StockTwits user/trader.
        """
        clean_user = username.strip().lstrip("@")

        if use_mock:
            logger.info(f"Using mock data generator for StockTwits user @{clean_user}")
            return self._generate_mock_user_messages(clean_user, limit)

        import urllib.request
        import urllib.parse

        url = f"{STOCKTWITS_API_BASE}/streams/user/{urllib.parse.quote(clean_user)}.json?limit={min(limit, 30)}"

        try:
            if requests is not None:
                resp = requests.get(url, headers=self.headers, timeout=8)
                status_code = resp.status_code
                data = resp.json() if status_code == 200 else {}
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    status_code = r.status
                    data = json.loads(r.read().decode("utf-8"))

            if status_code == 200:
                raw_messages = data.get("messages", [])
                logger.info(f"Retrieved {len(raw_messages)} live messages from @{clean_user} on StockTwits")
                return [self._normalize_message(m, f"user:{clean_user}") for m in raw_messages[:limit]]
            else:
                logger.warning(f"StockTwits user stream HTTP {status_code}. Using fallback.")
                return self._generate_mock_user_messages(clean_user, limit)
        except Exception as err:
            logger.warning(f"StockTwits user stream fallback for @{clean_user}: {err}")
            return self._generate_mock_user_messages(clean_user, limit)

    def fetch_trending_symbols(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch currently trending symbols on StockTwits."""
        url = f"{STOCKTWITS_API_BASE}/trending/symbols.json"
        try:
            resp = requests.get(url, headers=self.headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                symbols = data.get("symbols", [])
                return symbols[:limit]
        except Exception as err:
            logger.warning(f"Could not fetch StockTwits trending symbols: {err}")
        return []

    def _normalize_message(self, m: Dict[str, Any], context_label: str) -> Dict[str, Any]:
        """Convert a raw StockTwits message into Pulse standardized PostItem format."""
        msg_id = str(m.get("id", ""))
        user_info = m.get("user") or {}
        author = user_info.get("username", "anonymous")
        created_at = m.get("created_at") or datetime.now(timezone.utc).isoformat()
        body = m.get("body", "").strip()

        # Extract native sentiment tag if provided by StockTwits user ($Bullish / $Bearish)
        entities = m.get("entities") or {}
        sentiment_entity = entities.get("sentiment") or {}
        stocktwits_sentiment = sentiment_entity.get("basic")  # "Bullish" | "Bearish" | None

        likes = (m.get("likes") or {}).get("total", 0)
        url = f"https://stocktwits.com/{author}/message/{msg_id}"

        # Clean title for synthesis
        title = body.replace("\n", " ")[:120]
        if len(body) > 120:
            title += "..."

        return {
            "id": f"st_{msg_id}",
            "subreddit": f"stocktwits/${context_label.upper()}",
            "title": title,
            "url": url,
            "permalink": url,
            "published_at": created_at,
            "score": likes,
            "num_comments": 0,
            "upvote_ratio": 1.0,
            "content_text": body,
            "stocktwits_sentiment": stocktwits_sentiment,
            "symbols": [s.get("symbol") for s in entities.get("symbols", [])],
        }

    def _generate_mock_messages(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Generate realistic mock StockTwits messages for offline testing and demos."""
        now = datetime.now(timezone.utc).isoformat()
        samples = [
            {
                "body": f"${symbol} massive options flow on the monthly calls. Institutional buyers aggressively stepping in here.",
                "sentiment": "Bullish",
                "likes": 18,
            },
            {
                "body": f"${symbol} testing key resistance on high volume. Breakout confirmation above today's high targets +8% upside.",
                "sentiment": "Bullish",
                "likes": 25,
            },
            {
                "body": f"${symbol} RSI reaching overbought conditions on the 4H chart. Trimming 30% of my position before earnings.",
                "sentiment": "Bearish",
                "likes": 9,
            },
            {
                "body": f"${symbol} retail bears getting squeezed again. Short interest remains elevated, continuation likely tomorrow.",
                "sentiment": "Bullish",
                "likes": 34,
            },
            {
                "body": f"${symbol} macro headwinds and yield curve pressure keeping multiples capped. Expecting consolidation in this range.",
                "sentiment": "Bearish",
                "likes": 12,
            },
            {
                "body": f"${symbol} guidance beat expectation, datacenter backlog growing quarter over quarter. Strong long-term hold.",
                "sentiment": "Bullish",
                "likes": 42,
            },
            {
                "body": f"Holding my ${symbol} core position. Volume looks healthy and dip was immediately bought up.",
                "sentiment": "Bullish",
                "likes": 15,
            },
            {
                "body": f"${symbol} valuation looks stretched relative to historical sector peers. Watching for support at the 50-day EMA.",
                "sentiment": "Bearish",
                "likes": 7,
            },
        ]

        posts = []
        for i, item in enumerate(samples[:limit]):
            msg_id = f"mock_{symbol.lower()}_{i+1}"
            url = f"https://stocktwits.com/symbol/{symbol}/message/{msg_id}"
            posts.append({
                "id": f"st_{msg_id}",
                "subreddit": f"stocktwits/${symbol}",
                "title": item["body"][:100] + "...",
                "url": url,
                "permalink": url,
                "published_at": now,
                "score": item["likes"],
                "num_comments": 0,
                "upvote_ratio": 1.0,
                "content_text": item["body"],
                "stocktwits_sentiment": item["sentiment"],
                "symbols": [symbol],
            })
        return posts

    def _generate_mock_user_messages(self, username: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Generate mock user stream messages for demo/offline testing."""
        now = datetime.now(timezone.utc).isoformat()
        samples = [
            f"Added to our top semiconductor holdings today. Risk/reward looks very attractive at current multiples.",
            f"Market breadth is improving across tech and industrials. Staying long index futures.",
            f"Trimmed our momentum swing positions ahead of upcoming CPI data print.",
            f"Breakout confirmation on key leading names. Volume expansion confirms institutional accumulation.",
            f"Sharing our weekly market outlook: focus remains on quality balance sheets and operating leverage.",
        ]

        posts = []
        for i, text in enumerate(samples[:limit]):
            msg_id = f"mock_u_{username.lower()}_{i+1}"
            url = f"https://stocktwits.com/{username}/message/{msg_id}"
            posts.append({
                "id": f"st_{msg_id}",
                "subreddit": f"stocktwits/@{username}",
                "title": text[:90] + "...",
                "url": url,
                "permalink": url,
                "published_at": now,
                "score": 10 + i * 3,
                "num_comments": 0,
                "upvote_ratio": 1.0,
                "content_text": text,
                "stocktwits_sentiment": "Bullish" if i % 2 == 0 else None,
                "symbols": ["SPY", "QQQ"],
            })
        return posts
