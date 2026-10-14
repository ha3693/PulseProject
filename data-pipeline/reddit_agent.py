#!/usr/bin/env python3
"""
Pulse Platform - Reddit Market Signal Agent using LangChain.
Queries financial subreddits (r/investing, r/stocks, r/wallstreetbets).
Delegates to agents.reddit.market_agent.
"""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from agents.reddit.market_agent import RedditMarketAgent, PulseRedditAgent
from agents.cli import run_reddit


def main():
    parser = argparse.ArgumentParser(
        description="Pulse Reddit Market Signal Agent - Query r/investing, r/stocks, r/wallstreetbets"
    )
    parser.add_argument(
        "--topic",
        "-t",
        type=str,
        default="NVDA",
        help="Topic, asset ticker, or brand to query (e.g. 'NVDA', 'AAPL', 'Gold', 'Nike')"
    )
    parser.add_argument(
        "--window",
        "-w",
        type=str,
        default="week",
        choices=["24h", "day", "7d", "week", "month"],
        help="Time window for search ('24h', 'day', 'week', 'month')"
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=8,
        help="Maximum posts to retrieve per subreddit (default: 8)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional destination path for the JSON output file"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run using representative synthetic data (useful for offline testing or demo)"
    )

    args = parser.parse_args()
    run_reddit(args)


if __name__ == "__main__":
    main()
