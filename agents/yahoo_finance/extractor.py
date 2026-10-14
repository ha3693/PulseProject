"""Yahoo Finance EOD Feeds & News Extractor for Pulse.
Fetches real-time / End-of-Day market quotes and news articles via Yahoo Finance feeds.
Provides topic-to-symbol resolution (e.g. 'NVDA', 'Gold' -> GC=F/GLD, 'Nike' -> NKE),
EOD market metrics, and rich article metadata with mock fallback capability.
"""

import os
import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("YahooFinanceExtractor")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Pre-defined mapping for popular commodities, indices, and brand queries
KNOWN_TOPIC_MAPPINGS: Dict[str, Tuple[str, str]] = {
    "gold": ("GC=F", "Gold Futures (COMEX)"),
    "gold futures": ("GC=F", "Gold Futures (COMEX)"),
    "gld": ("GLD", "SPDR Gold Shares"),
    "silver": ("SI=F", "Silver Futures"),
    "slv": ("SLV", "iShares Silver Trust"),
    "crude oil": ("CL=F", "Crude Oil WTI Futures"),
    "oil": ("CL=F", "Crude Oil WTI Futures"),
    "brent": ("BZ=F", "Brent Crude Oil Futures"),
    "natural gas": ("NG=F", "Natural Gas Futures"),
    "copper": ("HG=F", "Copper Futures"),
    "bitcoin": ("BTC-USD", "Bitcoin USD"),
    "btc": ("BTC-USD", "Bitcoin USD"),
    "ethereum": ("ETH-USD", "Ethereum USD"),
    "eth": ("ETH-USD", "Ethereum USD"),
    "sp500": ("^GSPC", "S&P 500 Index"),
    "s&p 500": ("^GSPC", "S&P 500 Index"),
    "s&p": ("^GSPC", "S&P 500 Index"),
    "nasdaq": ("^IXIC", "NASDAQ Composite Index"),
    "dow": ("^DJI", "Dow Jones Industrial Average"),
    "dow jones": ("^DJI", "Dow Jones Industrial Average"),
    "nike": ("NKE", "NIKE, Inc."),
    "apple": ("AAPL", "Apple Inc."),
    "nvidia": ("NVDA", "NVIDIA Corporation"),
    "nvda": ("NVDA", "NVIDIA Corporation"),
    "tesla": ("TSLA", "Tesla, Inc."),
    "tsla": ("TSLA", "Tesla, Inc."),
    "microsoft": ("MSFT", "Microsoft Corporation"),
    "msft": ("MSFT", "Microsoft Corporation"),
    "google": ("GOOGL", "Alphabet Inc."),
    "alphabet": ("GOOGL", "Alphabet Inc."),
    "amazon": ("AMZN", "Amazon.com, Inc."),
    "amzn": ("AMZN", "Amazon.com, Inc."),
    "meta": ("META", "Meta Platforms, Inc."),
    "facebook": ("META", "Meta Platforms, Inc."),
}


def resolve_topic_to_symbol(topic: str) -> Tuple[Optional[str], str]:
    """
    Resolve a user query topic (e.g. 'NVDA', 'Gold', 'Nike') to a primary Yahoo Finance ticker and asset name.
    """
    normalized = topic.strip().lower()
    if normalized in KNOWN_TOPIC_MAPPINGS:
        return KNOWN_TOPIC_MAPPINGS[normalized]

    # Check if already an uppercase ticker like 'NVDA', 'AAPL', 'NKE'
    if topic.isupper() and 1 <= len(topic) <= 6 and topic.isalpha():
        return topic, f"{topic} Equity"

    # Dynamic search via yfinance
    try:
        import yfinance as yf
        search = yf.Search(topic, max_results=3, news_count=0)
        if search.quotes and len(search.quotes) > 0:
            first = search.quotes[0]
            symbol = first.get("symbol")
            name = first.get("shortname") or first.get("longname") or symbol
            logger.info(f"Resolved topic '{topic}' to symbol '{symbol}' ({name}) via search.")
            return symbol, name
    except Exception as e:
        logger.warning(f"Error resolving topic '{topic}' via yf.Search: {e}")

    # Fallback to uppercase query
    clean_topic = topic.strip().upper()
    return clean_topic, f"{topic.title()}"


def fetch_eod_market_data(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fetch End-of-Day (EOD) or latest trading session quotes and price statistics.
    """
    if not symbol:
        return None

    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        fast_info = getattr(ticker, "fast_info", None)

        last_price = None
        prev_close = None
        day_high = None
        day_low = None
        volume = None
        currency = "USD"

        if fast_info is not None:
            try:
                last_price = getattr(fast_info, "last_price", None)
                prev_close = getattr(fast_info, "previous_close", None)
                day_high = getattr(fast_info, "day_high", None)
                day_low = getattr(fast_info, "day_low", None)
                volume = getattr(fast_info, "last_volume", None)
                currency = getattr(fast_info, "currency", "USD")
            except Exception:
                pass

        # If fast_info was missing values, try history(period="5d")
        if last_price is None or prev_close is None:
            try:
                hist = ticker.history(period="5d")
                if not hist.empty:
                    last_price = float(hist["Close"].iloc[-1])
                    if len(hist) > 1:
                        prev_close = float(hist["Close"].iloc[-2])
                    day_high = float(hist["High"].iloc[-1])
                    day_low = float(hist["Low"].iloc[-1])
                    volume = int(hist["Volume"].iloc[-1])
            except Exception:
                pass

        if last_price is not None:
            last_price = round(float(last_price), 2)
            prev_close = round(float(prev_close), 2) if prev_close else last_price
            change = round(last_price - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

            return {
                "symbol": symbol,
                "name": symbol,
                "last_price": last_price,
                "previous_close": prev_close,
                "change": change,
                "change_percent": change_pct,
                "day_high": round(float(day_high), 2) if day_high is not None else None,
                "day_low": round(float(day_low), 2) if day_low is not None else None,
                "volume": int(volume) if volume is not None else None,
                "currency": currency or "USD",
                "market_state": "CLOSED",
                "as_of": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        logger.warning(f"Could not retrieve EOD market metrics for '{symbol}': {e}")

    return None


def _format_time_ago(epoch_sec: int) -> str:
    """Format Unix timestamp into a human-friendly relative string."""
    try:
        delta = datetime.now(timezone.utc).timestamp() - epoch_sec
        if delta < 0:
            delta = 0
        minutes = int(delta // 60)
        hours = int(minutes // 60)
        days = int(hours // 24)

        if days > 0:
            return f"{days}d ago"
        elif hours > 0:
            return f"{hours}h ago"
        elif minutes > 0:
            return f"{minutes}m ago"
        else:
            return "just now"
    except Exception:
        return "recently"


def _enrich_article_summary(url: str, timeout: int = 2) -> Optional[str]:
    """Attempt a fast fetch of the article page to extract the meta description or opening snippet."""
    if not url or not url.startswith("http"):
        return None

    try:
        from curl_cffi import requests
        from bs4 import BeautifulSoup

        resp = requests.get(url, impersonate="chrome", timeout=timeout)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            meta_desc = (
                soup.find("meta", attrs={"name": "description"})
                or soup.find("meta", attrs={"property": "og:description"})
            )
            if meta_desc and meta_desc.get("content"):
                desc = meta_desc.get("content").strip()
                if len(desc) > 20:
                    return desc

            for p in soup.find_all("p"):
                text = p.get_text().strip()
                if len(text) > 60 and "Coinbase" not in text and "cookie" not in text.lower():
                    return text[:300]
    except Exception:
        pass
    return None


def _enrich_articles_parallel(articles: List[Dict[str, Any]], max_articles: int = 5) -> None:
    """Enrich top articles with snippet descriptions concurrently."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_one(item: Dict[str, Any]):
        url = item.get("url") or item.get("link")
        if url:
            snippet = _enrich_article_summary(url, timeout=2)
            if snippet:
                item["summary"] = snippet
                item["content_text"] = snippet

    to_enrich = articles[:max_articles]
    with ThreadPoolExecutor(max_workers=min(len(to_enrich), 5)) as executor:
        futures = [executor.submit(_fetch_one, item) for item in to_enrich]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception:
                pass


def fetch_yahoo_finance_news(
    topic: str,
    limit: int = 10,
    use_mock: bool = False,
    enrich_snippets: bool = True
) -> Dict[str, Any]:
    """
    Extract Yahoo Finance EOD news feed and market data for the given topic.
    
    Args:
        topic: Query asset or subject (e.g. 'NVDA', 'Gold', 'Nike')
        limit: Maximum number of articles to retrieve
        use_mock: Whether to return representative synthetic data for offline/test use
        enrich_snippets: Whether to fetch meta descriptions / snippets for top articles
        
    Returns:
        Dict with 'success', 'topic', 'symbol', 'asset_name', 'market_data', and 'news_items'
    """
    resolved_symbol, asset_name = resolve_topic_to_symbol(topic)
    logger.info(f"Fetching Yahoo Finance EOD feeds for topic='{topic}' (symbol='{resolved_symbol}', name='{asset_name}')")

    if use_mock:
        return _get_mock_feed(topic, resolved_symbol, asset_name, limit)

    try:
        import yfinance as yf

        # Step 1: EOD Market Snapshot
        eod_data = fetch_eod_market_data(resolved_symbol) if resolved_symbol else None
        if eod_data and asset_name:
            eod_data["name"] = asset_name

        # Step 2: Fetch News via yf.Search with intelligent query variations
        queries_to_try = []
        clean_t = topic.strip()
        if clean_t.isupper() and len(clean_t) <= 5:
            queries_to_try.append(f"{clean_t} stock")
            queries_to_try.append(clean_t)
        elif asset_name and asset_name != clean_t:
            queries_to_try.append(f"{clean_t} stock")
            queries_to_try.append(clean_t)
        else:
            queries_to_try.append(clean_t)
            queries_to_try.append(f"{clean_t} stock")

        seen_links = set()
        articles = []

        for q in queries_to_try:
            try:
                search = yf.Search(q, max_results=5, news_count=max(limit, 6))
                raw_news = getattr(search, "news", []) or []
                for item in raw_news:
                    link = item.get("link", "")
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)

                    pub_time = item.get("providerPublishTime")
                    if pub_time:
                        try:
                            iso_time = datetime.fromtimestamp(pub_time, tz=timezone.utc).isoformat()
                            time_ago = _format_time_ago(pub_time)
                        except Exception:
                            iso_time = datetime.now(timezone.utc).isoformat()
                            time_ago = "recently"
                    else:
                        iso_time = datetime.now(timezone.utc).isoformat()
                        time_ago = "recently"

                    publisher_name = item.get("publisher", "Yahoo Finance")
                    title_text = item.get("title", "Untitled News")
                    articles.append({
                        "id": str(item.get("uuid") or hash(link)),
                        "subreddit": publisher_name,
                        "publisher": publisher_name,
                        "title": title_text,
                        "url": link,
                        "permalink": link,
                        "published_at": iso_time,
                        "time_ago": time_ago,
                        "score": 0,
                        "num_comments": 0,
                        "upvote_ratio": 1.0,
                        "content_text": title_text,
                        "related_tickers": item.get("relatedTickers", [resolved_symbol] if resolved_symbol else []),
                        "summary": None,
                    })

                    if len(articles) >= limit:
                        break
            except Exception as e:
                logger.warning(f"Error querying yf.Search('{q}'): {e}")

            if len(articles) >= limit:
                break

        # Step 3: Fast parallel snippet enrichment
        if enrich_snippets and articles:
            _enrich_articles_parallel(articles, max_articles=min(len(articles), 5))

        # Fallback to mock data if Yahoo returned 0 articles (network safeguard)
        if not articles:
            logger.warning(f"Yahoo Finance returned 0 news articles for '{topic}'. Using fallback mock feed.")
            return _get_mock_feed(topic, resolved_symbol, asset_name, limit)

        return {
            "success": True,
            "topic": topic,
            "symbol": resolved_symbol,
            "asset_name": asset_name,
            "market_data": eod_data,
            "news_items": articles,
        }

    except Exception as e:
        logger.error(f"Failed to fetch live Yahoo Finance feed for '{topic}': {e}. Falling back to mock data.")
        return _get_mock_feed(topic, resolved_symbol, asset_name, limit)


def _get_mock_feed(topic: str, symbol: Optional[str], asset_name: str, limit: int) -> Dict[str, Any]:
    """Generates realistic market and news payloads for offline development, tests, and demos."""
    now_iso = datetime.now(timezone.utc).isoformat()
    lower_t = topic.lower()

    def _normalize_mock_item(item: Dict[str, Any]) -> Dict[str, Any]:
        pub = item.get("publisher", "Yahoo Finance")
        link = item.get("link", "")
        title = item.get("title", "")
        return {
            "id": item.get("id", str(hash(link))),
            "subreddit": pub,
            "publisher": pub,
            "title": title,
            "url": link,
            "permalink": link,
            "published_at": item.get("published_at", now_iso),
            "time_ago": item.get("time_ago", "recently"),
            "score": 0,
            "num_comments": 0,
            "upvote_ratio": 1.0,
            "content_text": item.get("summary") or title,
            "related_tickers": item.get("related_tickers", [symbol] if symbol else []),
            "summary": item.get("summary") or title,
        }

    if "nvda" in lower_t or "nvidia" in lower_t:
        raw_items = [
            {
                "id": "mock-nvda-1",
                "title": "Nvidia Blackwell Ultra GPU Architecture Production Ramps Ahead of Schedule",
                "publisher": "Bloomberg Technology",
                "link": "https://finance.yahoo.com/news/nvidia-blackwell-gpu-production-ramps-ahead-schedule.html",
                "published_at": now_iso,
                "time_ago": "2h ago",
                "related_tickers": ["NVDA", "TSM", "AMD"],
                "summary": "Supply chain partners confirm Taiwan Semiconductor has cleared packaging bottlenecks for Nvidia's high-margin enterprise AI accelerators, paving the way for record hyperscaler deliveries.",
            },
            {
                "id": "mock-nvda-2",
                "title": "Morgan Stanley Reaffirms Top Pick on Nvidia: AI Data Center Capex Remains Robust",
                "publisher": "Investing.com",
                "link": "https://finance.yahoo.com/news/morgan-stanley-reaffirms-top-pick-nvidia-capex.html",
                "published_at": now_iso,
                "time_ago": "4h ago",
                "related_tickers": ["NVDA", "MSFT", "GOOGL"],
                "summary": "Analyst checks indicate big tech capital expenditures are pacing 20% higher than prior fiscal year estimates, with Nvidia capturing over 80% share of accelerated compute budgets.",
            },
            {
                "id": "mock-nvda-3",
                "title": "Regulatory Scrutiny: DOJ Explores Antitrust Inquiries into AI Bundling Practices",
                "publisher": "Reuters Financial",
                "link": "https://finance.yahoo.com/news/regulatory-scrutiny-doj-explores-antitrust-inquiries-ai.html",
                "published_at": now_iso,
                "time_ago": "7h ago",
                "related_tickers": ["NVDA"],
                "summary": "Federal regulators sent informal requests regarding CUDA software licensing terms and high-bandwidth memory allocation agreements with premier cloud providers.",
            }
        ]
        return {
            "success": True,
            "topic": "NVDA",
            "symbol": "NVDA",
            "asset_name": "NVIDIA Corporation",
            "market_data": {
                "symbol": "NVDA",
                "name": "NVIDIA Corporation",
                "last_price": 228.52,
                "previous_close": 226.32,
                "change": 2.20,
                "change_percent": 0.97,
                "day_high": 228.64,
                "day_low": 223.06,
                "volume": 48291000,
                "currency": "USD",
                "market_state": "CLOSED",
                "as_of": now_iso,
            },
            "news_items": [_normalize_mock_item(i) for i in raw_items][:limit]
        }
    elif "gold" in lower_t or "gld" in lower_t:
        raw_items = [
            {
                "id": "mock-gold-1",
                "title": "Central Bank Bullion Accumulation Hits Multi-Year High as Dollar Diversification Expands",
                "publisher": "Financial Times",
                "link": "https://finance.yahoo.com/news/central-bank-gold-accumulation-dollar-diversification.html",
                "published_at": now_iso,
                "time_ago": "3h ago",
                "related_tickers": ["GC=F", "GLD", "DX-Y.NYB"],
                "summary": "Sovereign reserves in Asia and emerging markets acquired another 45 metric tons in September, insulating national balance sheets from currency fluctuations.",
            },
            {
                "id": "mock-gold-2",
                "title": "Gold Dips Modestly on Stronger US Jobs Data and Elevated Treasury Yields",
                "publisher": "MarketWatch",
                "link": "https://finance.yahoo.com/news/gold-dips-modestly-stronger-us-jobs-yields.html",
                "published_at": now_iso,
                "time_ago": "5h ago",
                "related_tickers": ["GC=F", "^TNX"],
                "summary": "Benchmark 10-year US Treasury yields ticked up 4 basis points, creating short-term non-yielding asset headwinds despite underlying geopolitical demand.",
            }
        ]
        return {
            "success": True,
            "topic": "Gold",
            "symbol": "GC=F",
            "asset_name": "Gold Futures (COMEX)",
            "market_data": {
                "symbol": "GC=F",
                "name": "Gold Futures (COMEX)",
                "last_price": 4184.10,
                "previous_close": 4211.10,
                "change": -27.00,
                "change_percent": -0.64,
                "day_high": 4186.80,
                "day_low": 4177.40,
                "volume": 128450,
                "currency": "USD",
                "market_state": "CLOSED",
                "as_of": now_iso,
            },
            "news_items": [_normalize_mock_item(i) for i in raw_items][:limit]
        }
    elif "nike" in lower_t or "nke" in lower_t:
        raw_items = [
            {
                "id": "mock-nke-1",
                "title": "Nike CEO Direct-to-Consumer Pivot Review: Re-engaging Wholesale Partners Foot Locker and Dick's",
                "publisher": "Wall Street Journal",
                "link": "https://finance.yahoo.com/news/nike-ceo-direct-to-consumer-wholesale-partnerships.html",
                "published_at": now_iso,
                "time_ago": "2h ago",
                "related_tickers": ["NKE", "FL", "DKS"],
                "summary": "Nike leadership is aggressively repairing relationships with retail sporting goods partners to reclaim market shelf share lost to On Running and Hoka.",
            },
            {
                "id": "mock-nke-2",
                "title": "BofA Turns Bearish on Nike: What's Behind the Downgrade?",
                "publisher": "Insider Monkey",
                "link": "https://finance.yahoo.com/markets/stocks/articles/bofa-turns-bearish-nike-behind-141540425.html",
                "published_at": now_iso,
                "time_ago": "5h ago",
                "related_tickers": ["NKE"],
                "summary": "Bank of America lowered its rating to Neutral from Buy, citing prolonged consumer discretionary weakness in Greater China and inventory markdowns.",
            }
        ]
        return {
            "success": True,
            "topic": "Nike",
            "symbol": "NKE",
            "asset_name": "NIKE, Inc.",
            "market_data": {
                "symbol": "NKE",
                "name": "NIKE, Inc.",
                "last_price": 35.33,
                "previous_close": 35.23,
                "change": 0.10,
                "change_percent": 0.28,
                "day_high": 35.84,
                "day_low": 35.15,
                "volume": 22450100,
                "currency": "USD",
                "market_state": "CLOSED",
                "as_of": now_iso,
            },
            "news_items": [_normalize_mock_item(i) for i in raw_items][:limit]
        }
    else:
        sym = symbol or topic.upper()
        raw_items = [
            {
                "id": f"mock-{sym}-1",
                "title": f"Market Overview and Institutional Inflows for {asset_name}",
                "publisher": "Yahoo Finance News",
                "link": f"https://finance.yahoo.com/news/{sym.lower()}-market-overview.html",
                "published_at": now_iso,
                "time_ago": "3h ago",
                "related_tickers": [sym],
                "summary": f"Traders and asset managers digest end-of-day closing news for {asset_name} alongside macroeconomic benchmark shifts.",
            }
        ]
        return {
            "success": True,
            "topic": topic,
            "symbol": sym,
            "asset_name": asset_name,
            "market_data": {
                "symbol": sym,
                "name": asset_name,
                "last_price": 100.0,
                "previous_close": 99.5,
                "change": 0.5,
                "change_percent": 0.50,
                "day_high": 101.2,
                "day_low": 99.1,
                "volume": 1500000,
                "currency": "USD",
                "market_state": "CLOSED",
                "as_of": now_iso,
            },
            "news_items": [_normalize_mock_item(i) for i in raw_items][:limit]
        }
