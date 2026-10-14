# Pulse — Real-Time Sentiment & Market Signal Platform

> An AI assistant that condenses news, social sentiment, and asset price history into clear, source-cited analytical market signals.

---

## 📌 Problem & Purpose

Public opinion on stocks, commodities, and brands is scattered across disparate news outlets, social platforms, and forums. Reading through this volume manually is time-consuming and introduces cognitive bias based on the first few articles encountered.

**Pulse** bridges this gap. When a user queries a topic (e.g., `NVDA`, `Gold`, `Nike`), Pulse aggregates coverage across approved English-language sources within minutes, displaying:
1. **Real-time & Historical Sentiment**: Scored using LLMs and domain-specific NLP models (FinBERT).
2. **Sentiment vs. Price Movement**: Visualized with divergence flags on interactive charts.
3. **Source-Cited Syntheses**: Top drivers, praise, complaints, and direct source links.

Target user groups:
- **Retail Investors & Analysts**: Fast pre-trade sentiment diligence and divergence discovery.
- **Brand & PR Teams**: Tracking reputation trends, complaints, and competitor share-of-voice.
- **Researchers & Students**: Studying public opinion dynamics and financial sentiment correlations.

---

## 🔍 Core Features

### 1. Market Lens
- **Sentiment vs. Price Plot**: Dual-axis trend chart overlaying the **Pulse Index** (-100 to +100) against daily asset price action.
- **Divergence Alerts**: Highlights when price and sentiment move in opposite directions (e.g., price dips despite soaring bullish sentiment).
- **Multi-Asset Watchlist**: Compare real-time signals across tracked assets.
- **Backtesting Module**: Analyzes how frequently sentiment signals correlated with next-day price direction over 12 months of historical data.

### 2. Brand Lens
- **Praise vs. Complaint Breakdown**: Surfaces top positive catalysts and customer grievances.
- **Competitor Share of Voice**: Side-by-side volume and sentiment comparison against 1–2 key industry competitors.
- **Verified Source Attribution**: Every synthesized driver links back to the original article or post.

---

## 🏗️ Architecture & Technology Stack

| Layer | Technologies & Tools |
| :--- | :--- |
| **Frontend UI** | Next.js (App Router), React, Recharts, Vanilla CSS |
| **Database & Auth** | Supabase (PostgreSQL, Row-Level Security, Scheduled Ingestion) |
| **Data Ingestion & Pipeline** | Python 3.10+, `pandas`, `yfinance`, `praw` (Reddit API), `requests` |
| **NLP & Sentiment Benchmarking** | LLMs (Gemini / Claude / GPT) benchmarked against **FinBERT** (`transformers`, `torch`) |
| **Data Sources** | **News:** GDELT DOC 2.0 API, Finnhub, NewsAPI<br>**Social:** Reddit (r/investing, r/stocks, r/wallstreetbets), Bluesky, StockTwits<br>**Market:** Yahoo Finance EOD feeds |

---

## 🎯 Target Scope (Demo Milestone — Dec 9)

- **10–15 Pre-loaded Topics**:
  - **Tech Equities (10)**: Apple (`AAPL`), Microsoft (`MSFT`), NVIDIA (`NVDA`), Alphabet (`GOOGL`), Amazon (`AMZN`), Meta (`META`), Tesla (`TSLA`), AMD (`AMD`), Netflix (`NFLX`), Palantir (`PLTR`)
  - **Commodities**: Gold (`GC=F`)
  - **Crypto**: Bitcoin (`BTC-USD`)
  - **Brands**: Nike (`NKE`) vs. Adidas (`ADDYY`)
- **Historical Depth**: 12 months of historical daily price and sentiment data.
- **Source Constraints**: 4–6 approved English-language public sources. Excludes paywalled, login-gated, non-English, and image/video-only content.
- **Accuracy Target**: $\ge 75\text{--}80\%$ sentiment agreement against a hand-labeled benchmark of 200 real-world posts.

---

## 📂 Repository Structure

```
PulseProject/
├── .env.example              # Template for environment variables and API keys
├── .gitignore                # Comprehensive ignore rules (Node, Python, Supabase, OS)
├── CONTRIBUTING.md           # Branching strategy, commit conventions, code reviews
├── README.md                 # Project vision, architecture, and overview
├── main.py                   # Master agent dispatcher CLI
├── agents/                   # Unified Intelligence Agents Package
│   ├── __init__.py           # Agent registry and factory (get_agent)
│   ├── base.py               # BaseAgent class (common LLM setup, persistence)
│   ├── schemas.py            # Unified Pydantic schemas (SignalReport, PostItem)
│   ├── cli.py                # Unified CLI runner (python -m agents.cli ...)
│   ├── yahoo_finance/        # Yahoo Finance EOD Feeds & News Agent
│   │   ├── __init__.py
│   │   ├── agent.py          # YahooFinanceAgent implementation
│   │   └── extractor.py      # EOD feed, quotes & snippet extractor
│   └── reddit/               # Reddit Sentiment & Signal Agents
│       ├── __init__.py
│       ├── market_agent.py   # RedditMarketAgent (r/investing, r/stocks, r/wsb)
│       ├── user_agent.py     # RedditUserAgent (user tracking, e.g. u/OpenAI)
│       ├── client.py         # Reddit client with OAuth & public API fallbacks
│       ├── user_extractor.py # Reddit user submissions extractor
│       └── deduplicator.py   # PostDeduplicator for seen_posts.json
├── docs/                     # Architectural and data source specifications
│   ├── ARCHITECTURE.md       # High-level architecture and algorithm design
│   └── DATA_SOURCES.md       # API limits, data privacy, and source compliance
├── frontend/                 # Next.js web application
│   └── .gitkeep
├── data-pipeline/            # Data pipeline tools and runners
│   ├── requirements.txt      # Python dependencies (yfinance, pandas, transformers, etc.)
│   ├── reddit_agent.py       # Pipeline runner for Reddit Market agent
│   └── yahoo_finance_agent.py# Pipeline runner for Yahoo Finance agent
├── output/                   # Generated JSON market signals & reports
└── supabase/                 # Supabase configuration & database migrations
    ├── schema.sql            # Database schema (topics, raw_content, signals)
    └── migrations/
        └── .gitkeep
```

---

## 🚀 Quickstart for Team Members

### 1. Clone & Set Up Environment Variables
```bash
git clone <YOUR-GITHUB-REPO-URL>
cd PulseProject

# Copy environment template
cp .env.example .env
```
Fill in the required Supabase URL, API keys for LLMs, Finnhub, and Reddit.

### 2. Python Pipeline Setup
```bash
cd data-pipeline
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend Setup
*(Initialized in upcoming sprint via Next.js)*
```bash
cd frontend
npm install
npm run dev
```

---

## ⚖️ Ethics, Compliance & Disclaimer

- **No Investment Advice**: Pulse outputs are purely analytical, research-oriented signals. Nothing provided constitutes financial or investment advice.
- **Privacy & API Compliance**: We access public, authenticated APIs only. We do not store personal profile data or user identities—only post timestamps, text, source metadata, and engagement counts.
- **Cached Daily Scans**: Posts are ingested and scored once per daily refresh cycle to minimize compute overhead and prevent redundant queries.
