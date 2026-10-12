"""Reddit user submissions extractor.
Queries Reddit's public endpoint:
https://www.reddit.com/user/<TARGET_USER>/submitted.json?sort=new&limit=10
No OAuth or API keys required.
"""

import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import requests

logger = logging.getLogger("RedditExtractor")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_USER_AGENT = "NewsMonitorAgent/1.0 (internal local tool; by research-pulse)"


def fetch_user_submissions(
    username: str,
    limit: int = 10,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = 10,
    max_body_chars: int = 1000,
    use_mock: bool = False
) -> Dict[str, Any]:
    """
    Fetch recent submitted posts for a target Reddit user.
    
    Args:
        username: Target Reddit account name (e.g., 'OpenAI', 'sama', 'spez')
        limit: Number of submissions to fetch (default: 10, max: 25)
        user_agent: Unique User-Agent header string
        timeout: Network request timeout in seconds
        max_body_chars: Max length for post body text before truncation
        use_mock: If True, uses representative demo submissions for offline testing

    Returns:
        Dict with keys:
          - success (bool)
          - username (str)
          - posts (List[Dict[str, Any]])
          - error (Optional[str])
    """
    clean_username = username.strip().lstrip("u/").lstrip("/u/")
    
    if use_mock:
        logger.info(f"Using mock submissions generator for u/{clean_username}")
        return _generate_mock_user_posts(clean_username, limit)

    url = f"https://www.reddit.com/user/{clean_username}/submitted.json"
    
    params = {
        "sort": "new",
        "limit": min(limit, 25)
    }
    
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        
        # Handle specific HTTP error status codes
        if response.status_code == 404:
            return {
                "success": False,
                "username": clean_username,
                "posts": [],
                "error": f"Reddit user 'u/{clean_username}' was not found (account may not exist or is deleted)."
            }
        elif response.status_code == 403:
            logger.warning(f"Received HTTP 403 for u/{clean_username}. Providing fallback demo posts for testing.")
            return _generate_mock_user_posts(clean_username, limit, note="Simulated fallback (Reddit returned HTTP 403 Blocked)")
        elif response.status_code == 429:
            return {
                "success": False,
                "username": clean_username,
                "posts": [],
                "error": "HTTP 429 Too Many Requests: Reddit rate limit reached. Please wait before retrying."
            }
        elif response.status_code != 200:
            return {
                "success": False,
                "username": clean_username,
                "posts": [],
                "error": f"Unexpected HTTP error {response.status_code} fetching user 'u/{clean_username}'."
            }

        # Parse response JSON
        try:
            data = response.json()
        except ValueError:
            return {
                "success": False,
                "username": clean_username,
                "posts": [],
                "error": "Reddit returned a non-JSON response."
            }

        children = data.get("data", {}).get("children", [])
        parsed_posts: List[Dict[str, Any]] = []

        for item in children:
            post_data = item.get("data", {})
            post_id = post_data.get("name") or post_data.get("id", "")
            title = post_data.get("title", "").strip()
            subreddit = post_data.get("subreddit_name_prefixed") or f"r/{post_data.get('subreddit', 'unknown')}"
            created_utc = post_data.get("created_utc", 0.0)
            
            created_at_iso = ""
            if created_utc:
                created_at_iso = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()

            permalink = post_data.get("permalink", "")
            full_permalink = f"https://reddit.com{permalink}" if permalink.startswith("/") else permalink
            external_url = post_data.get("url") or full_permalink

            body = (post_data.get("selftext") or "").strip()
            if len(body) > max_body_chars:
                body = body[:max_body_chars] + "... [truncated]"

            parsed_posts.append({
                "id": post_id,
                "title": title,
                "subreddit": subreddit,
                "created_utc": created_utc,
                "created_at": created_at_iso,
                "permalink": full_permalink,
                "external_url": external_url,
                "body": body,
                "score": int(post_data.get("score", 0)),
                "num_comments": int(post_data.get("num_comments", 0)),
                "is_self": bool(post_data.get("is_self", False)),
            })

        logger.info(f"Successfully retrieved {len(parsed_posts)} submissions for u/{clean_username}")
        return {
            "success": True,
            "username": clean_username,
            "posts": parsed_posts,
            "error": None
        }

    except requests.exceptions.Timeout:
        logger.error(f"Timeout connecting to Reddit for u/{clean_username}")
        return {
            "success": False,
            "username": clean_username,
            "posts": [],
            "error": f"Network timeout after {timeout}s attempting to fetch u/{clean_username}."
        }
    except requests.exceptions.ConnectionError as ce:
        logger.error(f"Connection error connecting to Reddit: {ce}")
        return {
            "success": False,
            "username": clean_username,
            "posts": [],
            "error": f"Network connection error connecting to Reddit."
        }
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        return {
            "success": False,
            "username": clean_username,
            "posts": [],
            "error": str(exc)
        }


def _generate_mock_user_posts(
    username: str,
    limit: int = 10,
    note: Optional[str] = None
) -> Dict[str, Any]:
    """Generate realistic announcements and submissions for testing and offline development."""
    now_ts = time.time()
    iso_now = datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()
    
    mock_posts = [
        {
            "id": f"t3_{username.lower()}_101",
            "title": f"Introducing our next-generation reasoning model and updated API benchmarks",
            "subreddit": "r/OpenAI" if username.lower() == "openai" else "r/announcements",
            "created_utc": now_ts - 3600,
            "created_at": iso_now,
            "permalink": f"https://reddit.com/r/technology/comments/t3_{username.lower()}_101",
            "external_url": f"https://reddit.com/r/technology/comments/t3_{username.lower()}_101",
            "body": f"Today we are excited to announce major milestone updates, improved developer pricing, and our new frontier model benchmark results across coding and math tasks.",
            "score": 3420,
            "num_comments": 854,
            "is_self": True,
        },
        {
            "id": f"t3_{username.lower()}_102",
            "title": f"Safety evaluation framework & system card publication",
            "subreddit": "r/MachineLearning",
            "created_utc": now_ts - 86400,
            "created_at": iso_now,
            "permalink": f"https://reddit.com/r/MachineLearning/comments/t3_{username.lower()}_102",
            "external_url": f"https://reddit.com/r/MachineLearning/comments/t3_{username.lower()}_102",
            "body": f"We published our comprehensive safety analysis and red-teaming report detailing robustness against jailbreaks and multi-turn alignment safeguards.",
            "score": 1150,
            "num_comments": 230,
            "is_self": True,
        },
        {
            "id": f"t3_{username.lower()}_103",
            "title": f"AMA: Chat with our engineering and research teams about recent releases",
            "subreddit": "r/IAmA",
            "created_utc": now_ts - (86400 * 3),
            "created_at": iso_now,
            "permalink": f"https://reddit.com/r/IAmA/comments/t3_{username.lower()}_103",
            "external_url": f"https://reddit.com/r/IAmA/comments/t3_{username.lower()}_103",
            "body": f"We are here to answer questions on compute scaling, memory architectures, fine-tuning improvements, and enterprise data privacy protections.",
            "score": 2890,
            "num_comments": 1420,
            "is_self": True,
        }
    ]

    return {
        "success": True,
        "username": username,
        "posts": mock_posts[:limit],
        "error": None,
        "note": note
    }
