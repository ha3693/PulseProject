#!/usr/bin/env python3
"""
Pulse Platform - Reddit User AI News Monitoring Agent
Entry point: Fetches recent submissions from a target Reddit user via Reddit's public endpoint
(no OAuth / API keys needed) and generates an executive summary using LangChain.
"""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.agent import RedditUserNewsAgent
from src.deduplicator import PostDeduplicator


def main():
    parser = argparse.ArgumentParser(
        description="Pulse Reddit User News Monitoring Agent (No OAuth / API Keys Required)"
    )
    parser.add_argument(
        "--user",
        "-u",
        type=str,
        default="OpenAI",
        help="Target Reddit username to track (e.g. 'OpenAI', 'sama', 'spez')"
    )
    parser.add_argument(
        "--topic",
        "-t",
        type=str,
        default=None,
        help="Optional news topic or focus area to filter and prioritize (e.g. 'AI', 'GPT', 'safety')"
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Number of recent submissions to retrieve (default: 10)"
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
        help="Analyze all fetched posts, bypassing seen_posts.json deduplication"
    )
    parser.add_argument(
        "--clear-seen",
        action="store_true",
        help="Clear the seen posts cache before running"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use realistic demo submissions (useful for offline testing or demo)"
    )

    args = parser.parse_args()

    # Clear seen posts if requested
    if args.clear_seen:
        dedup = PostDeduplicator()
        dedup.clear()
        print("🧹 Cleared seen_posts.json cache.")

    print(f"\n🔍 Tracking Reddit submissions for u/{args.user}...")
    if args.topic:
        print(f"🎯 Focus topic: '{args.topic}'")

    agent = RedditUserNewsAgent()
    result = agent.run(
        username=args.user,
        topic=args.topic,
        limit=args.limit,
        only_new=not args.all,
        output_file=args.output,
        use_mock=args.mock
    )

    print("\n" + "=" * 65)
    print(f"📰 PULSE EXECUTIVE SUMMARY: u/{result.get('target_user')}")
    print("=" * 65)
    print(f"• Generated At:         {result.get('generated_at')}")
    print(f"• Total Posts Fetched:  {result.get('total_posts_fetched')}")
    print(f"• New Posts Analyzed:   {result.get('new_posts_analyzed')}")
    print(f"• Sentiment Signal:     {result.get('sentiment_signal', 'N/A').upper()}")
    
    if result.get("key_themes"):
        print(f"• Key Themes:           {', '.join(result.get('key_themes'))}")
    
    print("-" * 65)
    print(f"Executive Synthesis:\n{result.get('executive_summary')}")
    print("-" * 65)

    milestones = result.get("announcements_and_milestones", [])
    if milestones:
        print("📌 Key Announcements & Milestones:")
        for m in milestones:
            print(f"  - {m}")
        print("-" * 65)

    posts = result.get("posts", [])
    if posts:
        print(f"📋 Analyzed Posts ({len(posts)}):")
        for idx, p in enumerate(posts[:5], 1):
            print(f"  {idx}. [{p.get('subreddit')}] {p.get('title')}")
            print(f"     URL: {p.get('permalink')}")
            if p.get("summary"):
                print(f"     Takeaway: {p.get('summary')}")
        if len(posts) > 5:
            print(f"  ... and {len(posts) - 5} more in the output JSON file.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
