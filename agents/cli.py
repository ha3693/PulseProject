#!/usr/bin/env python3
"""
Pulse Unified Agent CLI Runner.
Command-line interface to execute any Pulse agent across Yahoo Finance, Reddit Market, and Reddit User.
"""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from agents import (
    YahooFinanceAgent,
    RedditMarketAgent,
    RedditUserAgent,
)


def run_yahoo(args):
    agent = YahooFinanceAgent()
    result = agent.run(
        topic=args.topic,
        time_window=args.window,
        limit=args.limit,
        output_file=args.output,
        use_mock=args.mock,
    )
    _print_signal_report("Yahoo Finance EOD", result)


def run_reddit(args):
    agent = RedditMarketAgent()
    result = agent.run(
        topic=args.topic,
        time_window=args.window,
        limit_per_sub=args.limit,
        output_file=args.output,
        use_mock=args.mock,
    )
    _print_signal_report("Reddit Market Signal", result)


def run_reddit_user(args):
    agent = RedditUserAgent()
    result = agent.run(
        username=args.user,
        topic=args.topic,
        limit=args.limit,
        only_new=not args.all,
        output_file=args.output,
        use_mock=args.mock,
    )

    print("\n" + "=" * 65)
    print(f"📰 PULSE EXECUTIVE SUMMARY: u/{result.get('target_user')}")
    print("=" * 65)
    print(f"• Generated At:         {result.get('generated_at')}")
    print(f"• Total Posts Fetched:  {result.get('total_posts_fetched')}")
    print(f"• New Posts Analyzed:   {result.get('new_posts_analyzed')}")
    print(f"• Sentiment Signal:     {str(result.get('sentiment_signal', 'N/A')).upper()}")
    if result.get("key_themes"):
        print(f"• Key Themes:           {', '.join(result.get('key_themes'))}")
    print("-" * 65)
    print(f"Executive Synthesis:\n{result.get('executive_summary')}")
    print("=" * 65 + "\n")


def _print_signal_report(source_label: str, result: dict):
    print("\n" + "=" * 65)
    print(f"📊 Pulse {source_label} Report for: {result.get('topic')}")
    print(f"Index Score: {result.get('aggregate_sentiment_score')} (-100 to +100)")
    print(f"Breakdown: {result.get('sentiment_breakdown')}")
    print(f"Posts Scanned: {result.get('total_posts_retrieved')} | Relevant: {result.get('relevant_posts_count')}")
    print("=" * 65)

    market = result.get("market_context")
    if market and market.get("last_price") is not None:
        last_p = market.get("last_price")
        chg = market.get("change", 0.0)
        chg_pct = market.get("change_percent", 0.0)
        sign = "+" if chg >= 0 else ""
        print(f"• EOD Closing Price:    ${last_p:,.2f} ({sign}{chg:.2f}, {sign}{chg_pct:.2f}%)")
        if market.get("day_low") is not None and market.get("day_high") is not None:
            print(f"• Day Range:            ${market.get('day_low', 0):,.2f} - ${market.get('day_high', 0):,.2f}")
        if market.get("volume"):
            print(f"• Session Volume:       {market.get('volume'):,}")
        print("-" * 65)

    print(f"Synthesis:\n{result.get('synthesis')}")
    print("=" * 65)

    catalysts = result.get("key_positive_catalysts", [])
    if catalysts:
        print("🚀 Positive Catalysts:")
        for c in catalysts:
            print(f"  + {c}")
        print("-" * 65)

    risks = result.get("key_risk_factors", [])
    if risks:
        print("⚠️ Downside Risks & Headwinds:")
        for r in risks:
            print(f"  - {r}")
        print("-" * 65)

    posts = result.get("posts", [])
    if posts:
        print(f"📰 Ingested Posts ({len(posts)}):")
        for idx, p in enumerate(posts[:5], 1):
            sent = p.get("sentiment_label", "neutral").upper()
            score = p.get("sentiment_score", 0.0)
            rel = "✓" if p.get("is_relevant", True) else "✗"
            print(f"  {idx}. [{rel} {sent} {score:+0.1f}] {p.get('title')}")
            print(f"     Source: {p.get('subreddit')} | URL: {p.get('url')}")
            if p.get("relevance_reason"):
                print(f"     Reason: {p.get('relevance_reason')}")
            print()
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Pulse Multi-Agent Intelligence System"
    )
    subparsers = parser.add_subparsers(dest="agent", required=True, help="Agent to run")

    # Yahoo Finance Agent subparser
    yahoo_parser = subparsers.add_parser("yahoo", help="Yahoo Finance EOD Feeds & News Agent")
    yahoo_parser.add_argument("--topic", "-t", type=str, default="NVDA", help="Asset ticker, commodity, or brand")
    yahoo_parser.add_argument("--window", "-w", type=str, default="day", choices=["24h", "day", "week", "month"])
    yahoo_parser.add_argument("--limit", "-l", type=int, default=6, help="Maximum articles to retrieve")
    yahoo_parser.add_argument("--output", "-o", type=str, default=None, help="Custom output JSON filepath")
    yahoo_parser.add_argument("--mock", action="store_true", help="Run with representative mock data")
    yahoo_parser.set_defaults(func=run_yahoo)

    # Reddit Market Agent subparser
    reddit_parser = subparsers.add_parser("reddit", help="Reddit Financial Subreddits Signal Agent")
    reddit_parser.add_argument("--topic", "-t", type=str, default="NVDA", help="Topic to query across subreddits")
    reddit_parser.add_argument("--window", "-w", type=str, default="week", choices=["24h", "day", "week", "month"])
    reddit_parser.add_argument("--limit", "-l", type=int, default=8, help="Max posts per subreddit")
    reddit_parser.add_argument("--output", "-o", type=str, default=None, help="Custom output JSON filepath")
    reddit_parser.add_argument("--mock", action="store_true", help="Run with representative mock data")
    reddit_parser.set_defaults(func=run_reddit)

    # Reddit User Agent subparser
    user_parser = subparsers.add_parser("reddit-user", help="Reddit User Profile Monitoring Agent")
    user_parser.add_argument("--user", "-u", type=str, default="OpenAI", help="Target Reddit username")
    user_parser.add_argument("--topic", "-t", type=str, default=None, help="Optional topic filter")
    user_parser.add_argument("--limit", "-l", type=int, default=10, help="Max submissions to retrieve")
    user_parser.add_argument("--all", action="store_true", help="Analyze all submissions bypassing deduplication")
    user_parser.add_argument("--output", "-o", type=str, default=None, help="Custom output JSON filepath")
    user_parser.add_argument("--mock", action="store_true", help="Run with representative mock data")
    user_parser.set_defaults(func=run_reddit_user)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
