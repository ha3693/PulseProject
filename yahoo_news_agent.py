#!/usr/bin/env python3
"""
Pulse Platform - Yahoo Finance EOD News Monitoring Agent.
Runner forwarding to agents.yahoo_finance.
"""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from agents.yahoo_finance.agent import YahooFinanceAgent
from agents.cli import run_yahoo
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Pulse Yahoo Finance EOD News Monitoring Agent (LangChain-powered)"
    )
    parser.add_argument("--topic", "-t", type=str, default="NVDA", help="Asset ticker, commodity, or brand")
    parser.add_argument("--window", "-w", type=str, default="day", choices=["24h", "day", "week", "month"])
    parser.add_argument("--limit", "-l", type=int, default=6, help="Maximum articles to retrieve")
    parser.add_argument("--output", "-o", type=str, default=None, help="Custom output JSON filepath")
    parser.add_argument("--mock", action="store_true", help="Run with representative mock data")

    args = parser.parse_args()
    run_yahoo(args)


if __name__ == "__main__":
    main()
