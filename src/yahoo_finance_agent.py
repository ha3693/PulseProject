"""Backward compatibility bridge for YahooFinanceAgent.
Re-exports from agents.yahoo_finance.agent.
"""

from agents.yahoo_finance.agent import (
    YahooFinanceAgent,
    extract_yahoo_eod_news_tool,
    get_eod_market_quote_tool,
    logger,
    main,
)
from agents.base import get_llm

__all__ = [
    "YahooFinanceAgent",
    "extract_yahoo_eod_news_tool",
    "get_eod_market_quote_tool",
    "get_llm",
    "logger",
    "main",
]

if __name__ == "__main__":
    main()
