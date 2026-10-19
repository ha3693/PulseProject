#!/usr/bin/env python3
"""
Pulse Platform - Master Agent Dispatcher.
Executes any Pulse agent across Yahoo Finance EOD feeds, Reddit Market subreddits, or Reddit User tracking.
"""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from agents.cli import (
    run_yahoo,
    run_reddit,
    run_reddit_user,
    run_stocktwits,
    run_stocktwits_user,
    run_bluesky,
    run_bluesky_user,
)


def main():
    parser = argparse.ArgumentParser(
        description="Pulse Market Intelligence & Sentiment Agent System",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--agent",
        "-a",
        type=str,
        default=None,
        choices=["yahoo", "reddit", "reddit-user", "stocktwits", "stocktwits-user", "bluesky", "bluesky-user"],
        help=(
            "Agent to run:\n"
            "  'yahoo': Yahoo Finance EOD feeds & news\n"
            "  'reddit': Reddit financial subreddits (r/investing, r/stocks, r/wsb)\n"
            "  'reddit-user': Reddit user profile monitoring\n"
            "  'stocktwits': StockTwits real-time retail sentiment & options chatter\n"
            "  'stocktwits-user': StockTwits trader/analyst stream monitoring\n"
            "  'bluesky': Bluesky conversational microblogging & tech sentiment\n"
            "  'bluesky-user': Bluesky account/organization feed tracking"
        )
    )
    parser.add_argument(
        "--topic",
        "-t",
        type=str,
        default=None,
        help="Asset ticker, commodity, or brand query (e.g. 'NVDA', 'Gold', 'Nike', 'AAPL')"
    )
    parser.add_argument(
        "--user",
        "-u",
        type=str,
        default=None,
        help="Target account handle (e.g. Reddit 'OpenAI', StockTwits 'howardlindzon', Bluesky 'bsky.app')"
    )
    parser.add_argument(
        "--window",
        "-w",
        type=str,
        default="day",
        choices=["24h", "day", "week", "month"],
        help="Time window evaluated (default: 'day')"
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=6,
        help="Maximum posts or news articles to retrieve (default: 6)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Custom output JSON filepath"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Bypass deduplication cache (user monitoring agents)"
    )
    parser.add_argument(
        "--clear-seen",
        action="store_true",
        help="Clear seen_posts.json deduplication cache"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run using representative synthetic data (offline / test mode)"
    )

    args = parser.parse_args()

    # Clear seen posts if requested
    if args.clear_seen:
        from agents.reddit.deduplicator import PostDeduplicator
        dedup = PostDeduplicator()
        dedup.clear()
        print("🧹 Cleared seen_posts.json cache.")

    # Determine default agent based on arguments provided
    selected_agent = args.agent
    if not selected_agent:
        if args.user:
            selected_agent = "reddit-user"
        else:
            selected_agent = "yahoo"

    is_user_agent = selected_agent in ["reddit-user", "stocktwits-user", "bluesky-user"]

    # Set default topic if not supplied
    if not args.topic and not is_user_agent:
        args.topic = "NVDA"

    if selected_agent == "yahoo":
        run_yahoo(args)
    elif selected_agent == "reddit":
        args.window = "week" if args.window == "day" else args.window
        run_reddit(args)
    elif selected_agent == "reddit-user":
        args.user = args.user or "OpenAI"
        run_reddit_user(args)
    elif selected_agent == "stocktwits":
        args.limit = max(args.limit, 15)
        run_stocktwits(args)
    elif selected_agent == "stocktwits-user":
        args.user = args.user or "howardlindzon"
        args.limit = max(args.limit, 10)
        run_stocktwits_user(args)
    elif selected_agent == "bluesky":
        args.window = "week" if args.window == "day" else args.window
        args.limit = max(args.limit, 10)
        run_bluesky(args)
    elif selected_agent == "bluesky-user":
        args.user = args.user or "bsky.app"
        args.limit = max(args.limit, 10)
        run_bluesky_user(args)


if __name__ == "__main__":
    main()
