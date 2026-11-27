# Pulse — Real-Time Sentiment & Market Signal Platform
> **MBA Term Project Report & Presentation Source Brief**  
> *Structured to satisfy all 6 Term Project Deliverables and serve as a complete, non-technical source document for slide-deck generation.*

---

## Deliverable 1: System Purpose, Business Problem, Users & Value Proposition

### 1.1 The Business & Societal Problem
Every day, millions of opinions about public companies, commodities, cryptocurrencies, and consumer brands are published across financial news outlets, Reddit forums, and social networks. For investors, corporate teams, and researchers, this creates three major challenges:
1. **Fragmented Attention**: Market-moving signals are scattered across institutional press, retail trading boards, and tech communities.
2. **Slow Manual Research & Cognitive Bias**: Analysts and retail investors who read only the first 5–10 headlines suffer from *availability bias*, waste hours switching tabs, and miss early shifts in public mood.
3. **Generic AI Misunderstands Finance**: Standard AI chatbots often misread financial slang (e.g., *"short squeeze"*, *"calls printing"*, *"bag holding"*) or confuse brand names with everyday words (e.g., *Apple* the tech giant vs. the fruit; *Gold* the commodity vs. video-game currency).

### 1.2 Potential Users & Fit Within Existing Business Environments
Pulse is designed for three primary user groups and plugs directly into their daily workflows without replacing their core tools:

| User Persona | Pain Point Today | How Pulse Fits Into Their Workflow & Adds Value |
| :--- | :--- | :--- |
| **Retail Investors & Equity Analysts** | Spend 60+ minutes scanning news, Reddit, and price charts before trades; vulnerable to herd panic. | Acts as a **morning pre-trade briefing cockpit** (`/terminal`): surfaces a single `-100` to `+100` sentiment score, 12-month price overlay, and divergence alerts in seconds. |
| **Brand, Marketing & PR Teams** | React too late to viral customer complaints or struggle to measure brand perception vs. rivals. | Integrates into **weekly brand-health & competitive reviews** via the **Brand Lens** (e.g., **Nike vs. Adidas**): quantifies Share of Voice, praise catalysts, and customer complaints with clickable source links. |
| **Academic & Market Researchers** | Lack clean, labeled, multi-source datasets linking public opinion to asset price action. | Provides **structured, backtestable historical data** (252 trading days) and a dual-AI benchmark comparing LLMs against FinBERT. |

### 1.3 High-Level Functionality (How It Works in General Terms)
Pulse continuously gathers public coverage across 5 live channels, filters out irrelevant noise, scores sentiment using a **dual-AI validation engine** (a generative LLM + Hugging Face **FinBERT**), weights each item by **source credibility** and **recency**, and pairs the resulting **Pulse Index (`-100` to `+100`)** against real stock/asset prices to flag **divergences** and backtest next-day predictive accuracy.

### 1.4 Target Scope (14 Core Tracked Assets)
- **10 Major Tech Equities**: NVIDIA (`NVDA`), Apple (`AAPL`), Microsoft (`MSFT`), Alphabet (`GOOGL`), Amazon (`AMZN`), Meta (`META`), Tesla (`TSLA`), AMD (`AMD`), Netflix (`NFLX`), Palantir (`PLTR`).
- **Commodities & Crypto**: Gold Futures (`GC=F`) and Bitcoin (`BTC-USD`).
- **Consumer Brand Rivalry**: Nike (`NKE`) vs. Adidas (`ADDYY`).

---

## Deliverable 2: Access to the Developed Software (Working Prototype)

- **GitHub Repository (Source Code & Version History)**: `https://github.com/ha3693/PulseProject.git` *(active branch: `brainstorm` / `main`)*
- **Cloud Deployment Architecture**: Configured for **Vercel** (`vercel.json`) with dual-runtime service bindings (Next.js frontend + Python serverless agent endpoint).
- **Quick Local Run & Evaluation Instructions**:
  1. **Web Application (Next.js 14)**:
     ```bash
     cd frontend && npm install && npm run dev
     # Open http://localhost:3000 (Market Overview) & http://localhost:3000/terminal
     ```
     *Note: Includes `pulse_snapshot.json` fast-cache so evaluators can test all 14 assets, 12-month charts, Brand Lens, and Backtesting immediately—even without external API keys.*
  2. **Python Multi-Agent CLI (Test Individual Agents or Full Pipeline)**:
     ```bash
     python main.py --agent reddit --topic NVDA --mock
     python main.py --agent gdelt --topic NVDA --mock
     python3 agents/scheduler.py --trigger manual_eval
     ```

---

## Deliverable 3: Detailed System Functionality, Modules, Prompts, Data Sources & Storage

### 3.1 System Modules
1. **Intelligence Agent Fleet (`agents/`)**: 8 specialized Python agents built on a shared `BaseAgent` class:
   - **5 Market Agents**: `YahooFinanceAgent`, `GdeltAgent`, `RedditMarketAgent`, `StockTwitsMarketAgent`, `BlueskyMarketAgent`.
   - **3 Social Radar (User-Tracking) Agents**: `RedditUserAgent`, `StockTwitsUserAgent`, `BlueskyUserAgent` (tracking high-signal voices like `u/OpenAI`, `howardlindzon`, `bsky.app`).
2. **Dual-Engine NLP & Scoring Core (`agents/finbert.py`, `agents/base.py`)**:
   - **FinBERT (`ProsusAI/finbert`)**: Runs locally via PyTorch to classify financial valence and provide an objective domain baseline.
   - **LangChain LLM Layer**: Connects to OpenAI (`gpt-4o-mini`) or Google Gemini (`gemini-1.5-flash`) with automatic fallback to offline FinBERT heuristics if API keys are unavailable.
3. **Orchestration & Math Engine (`agents/scheduler.py`)**:
   - `PulseIngestionOrchestrator` runs all agents, computes the weighted Pulse Index, detects 5-day price-sentiment divergences, and synchronizes results.
4. **Backend APIs (`api/index.py` & `frontend/app/api/`)**:
   - Python serverless service (`GET /health`, `POST /ingest`) bound to Next.js routes (`/api/ingest`, `/api/watchlist`).
5. **Interactive Frontend (`frontend/`)**:
   - Built with **Next.js 14 & React**: Market Overview Heatmap (`/`), Deep-Dive Terminal (`/terminal`), Personal Dashboard (`/dashboard`), Watchlist (`/watchlist`), and Auth (`/login`).

### 3.2 How the AI Prompts Work (Prompt Engineering Design)
Every LangChain agent uses a structured system prompt (`ChatPromptTemplate`) designed around four strict rules:
1. **Entity Disambiguation**: Explicitly instructs the AI to verify financial relevance (e.g., *"Apple"* = AAPL, not the fruit; *"Gold"* = commodity/futures, not gaming currency) and mark off-topic posts `is_relevant: false`.
2. **Financial Slang Calibration**: Guides the model on retail terminology—recognizing *"short squeeze"*, *"calls printing"*, *"buying the dip"*, and *"diamond hands"* as bullish, while flagging *"bag holding"*, *"dump"*, and *"rug pull"* as bearish.
3. **Theme Tagging**: Extracts structured tags (e.g., `earnings`, `guidance`, `macro`, `options_flow`, `antitrust`).
4. **Structured JSON Synthesis**: Forces valid JSON output containing an overall score (`-100` to `+100`), 2–3 positive catalysts, 2–3 risk factors, a 2–3 paragraph executive synthesis, and per-post confidence scores.

### 3.3 News & Market Data Sources (Credibility & Recency Weighting)
Pulse strictly uses **official public APIs and open data** (zero paywall bypassing, zero personal PII stored):

| Channel | Source | Credibility Weight | Purpose |
| :--- | :--- | :--- | :--- |
| **Market Pricing & News** | **Yahoo Finance** | **1.35×** *(Highest)* | 252 trading days (12 months) of daily OHLCV prices, volume, and Wall Street news. |
| **Global Press** | **GDELT DOC 2.0** | **1.30×** | Worldwide news monitoring, macro policy shifts, and international press coverage. |
| **Retail Investing** | **Reddit** (`r/investing`, `r/stocks`, `r/wallstreetbets`) | **1.00×** | Retail due diligence, grassroots sentiment, and emerging trends (with live RSS fallback). |
| **Trader Streams** | **StockTwits** | **0.95×** | Real-time `$Bullish`/`$Bearish` trader tags and options-flow sentiment. |
| **Open Social** | **Bluesky** (AT Protocol) | **0.90×** | Tech community, AI researcher, and early-adopter discourse. |

*Supplementary documented sources: Finnhub and NewsAPI free tiers (`docs/DATA_SOURCES.md`).*

**Time-Decay & Aggregation Formula**:  
Each post's influence decays exponentially over time ($r_i = e^{-\lambda \Delta t}$ over a 7-day window) and is multiplied by source credibility ($w_i = r_i \times c_i$), ensuring breaking news from 2 hours ago outweighs 5-day-old chatter.

### 3.4 Data Organization & Access (Supabase PostgreSQL + Fast Cache)
Data is organized in **Supabase PostgreSQL** (`supabase/schema.sql`) across 7 relational tables protected by **Row-Level Security (RLS)** and automated **6-hour `pg_cron` schedules**:
- `topics`: Master registry of the 14 tracked equities, commodities, crypto, and brands.
- `raw_content`: Deduplicated articles and social posts (unique constraint on `source + external_id`).
- `sentiment_items`: Individual LLM & FinBERT scores, confidence levels, and theme tags.
- `daily_sentiment_signals`: Daily aggregated Pulse Index, synthesis text, top drivers, and `divergence_flag`.
- `asset_prices`: 252 trading days of daily Open/High/Low/Close/Volume and daily returns.
- `user_watchlists` & `profiles`: Private, RLS-protected user watchlists and custom thesis notes.
- **Supabase-First Loading + Smart Freshness Banner (`loadPulseData.ts` & `DataFreshnessBanner.tsx`)**: On page load, the web app queries Supabase PostgreSQL first for instant rendering (falling back to `pulse_snapshot.json` only if offline) and clearly displays **`Data last updated on: <date & time>`**. If the dataset is **more than 1 hour old**, a non-blocking banner lets the user choose to **Refresh Data Now** or **Keep Current Data**—guaranteeing sub-second load times without unexpected 2-minute waits.

---

## Deliverable 4: Specific End-to-End Use Case (NVIDIA `NVDA` Bullish Divergence)

To see how Pulse works in practice, consider a **pre-market equity diligence scenario for NVIDIA (`NVDA`)**:

1. **Trigger**: A user opens `/terminal?asset=nvda` (or clicks **Live Scan (NVDA)**), or the 6-hour scheduled pipeline runs `PulseIngestionOrchestrator.run_for_topic("NVDA")`.
2. **Multi-Channel Ingestion**:
   - Yahoo Finance pulls `NVDA` closing price (**\$176.80**, down **-5.27%**) and recent analyst coverage.
   - GDELT, Reddit (`r/investing`, `r/stocks`, `r/wallstreetbets`), StockTwits, and Bluesky fetch **18 fresh, deduplicated items**.
3. **Dual-AI Scoring & Disambiguation**:
   - **FinBERT** scores every post on-device (`+0.6` baseline), correctly reading terms like *"buying the dip"* and *"datacenter backlog"* as positive.
   - **LangChain LLM** filters out off-topic noise, confirms **94.2% agreement** with FinBERT, and extracts positive catalysts (e.g., constructive Wall Street coverage) alongside risk factors (e.g., competitive chip concerns).
4. **Weighted Synthesis & Divergence Detection**:
   - Applying credibility weights (`Yahoo 1.35×` down to `Bluesky 0.90×`) and exponential time-decay yields a **Pulse Index of `+8.3`**.
   - **Business Insight**: Even though `NVDA` stock fell `-5.27%`, public and institutional sentiment rose to `+8.3`. Pulse raises a yellow **⚡ Bullish Divergence Alert**, signaling to the analyst that the sell-off may be macro-driven rather than a fundamental breakdown—with all 18 clickable source citations ready for verification.

---

## Deliverable 5: Broader Capabilities, Impact, Integration & Future Roadmap

### 5.1 Organizational & Societal Impact
- **Democratizing Institutional Intelligence**: Gives individual investors, students, and mid-sized brands the same multi-source sentiment analytics typically locked behind expensive institutional terminals.
- **Reducing Herd Panic & Misinformation**: By grounding every summary in clickable primary sources and a deterministic FinBERT baseline, Pulse counters sensationalist clickbait and emotional trading.
- **Early-Warning Brand Crisis Detection**: PR and risk teams can spot rising negative consumer sentiment days before it impacts quarterly sales.

### 5.2 Enterprise IT Infrastructure Integration
- **API-First Microservice**: Any internal corporate dashboard, Slack/Teams bot, or trading workflow can consume JSON signals from `POST /api/ingest` or `GET /api/ingest`.
- **Database & BI Connectivity**: Because all signals live in standard **Supabase PostgreSQL**, organizations can connect Tableau, Power BI, Looker, or internal Python notebooks directly to `daily_sentiment_signals` and `asset_prices`.
- **Cloud-Native Deployment**: Runs on serverless Node.js + Python (Vercel) with **LangSmith** telemetry for enterprise AI auditing.

### 5.3 Future Releases & Long-Term Evolution
- **Expanded Data Sources**: Integration of **X (Twitter)** API, **SEC EDGAR filings (10-K/10-Q)**, and **earnings call audio transcripts**.
- **Real-Time Alerting**: Automated Slack, email, and SMS webhooks triggered the moment a `⚡ Divergence Alert` or sharp brand-reputation drop occurs.
- **Multi-Language Global Sentiment**: Extending beyond English-only sources to capture European and Asian market sentiment around global brands and supply chains.
- **Custom User Topic Onboarding**: Allowing paying subscribers to add any custom ticker, private competitor, or product launch to the live 6-hour ingestion pipeline.

---

## Deliverable 6: 5-Minute In-Class Presentation & Live Demo Plan (Dec 9)

| Time | Segment | Key Talking Points & Demo Action |
| :--- | :--- | :--- |
| **0:00 – 0:50** | **The Problem & Vision** | Why manual news/social research fails (noise, bias, financial slang). Introduce **Pulse** and its `-100` to `+100` calibrated index. |
| **0:50 – 1:40** | **How We Built It (Story & Tech)** | Built step-by-step via **GitHub PRs #1–#6**: 8 **LangChain** agents + **FinBERT** guardrail + **LangSmith** observability + **Supabase** + **Vercel**. |
| **1:40 – 3:30** | **Live Demo (Prototype)** | 1) Show **Market Overview (`/`)**: 14-asset heatmap & KPIs.<br>2) Open **NVDA Terminal (`/terminal`)**: show **Bullish Divergence** (`-5.27%` price vs. `+8.3` Pulse), 5-agent weights, and source citations.<br>3) Briefly click **Brand Lens** (**Nike vs. Adidas**) & **Backtesting Lab**. |
| **3:30 – 4:20** | **Business Impact & Integration** | Value for analysts, PR teams, and researchers; zero-PII ethics; enterprise API/BI integration. |
| **4:20 – 5:00** | **Future Roadmap & Q&A** | SEC filings, earnings calls, real-time Slack alerts, and multi-language expansion. |

---

## Appendix: Our Step-by-Step Build Story (Grounded in GitHub History)

- **Chapter 1 — Blueprint & Ethics (`3c093c7`)**: Initialized GitHub repo, database schema (`supabase/schema.sql`), and strict zero-PII data rules (`docs/DATA_SOURCES.md`).
- **Chapter 2 — Agent #1: Reddit + RSS Resilience (`PR #1`)**: Built the first LangChain Reddit agent and solved OAuth roadblocks with a live RSS fallback.
- **Chapter 3 — Market Reality: Yahoo Finance (`PR #2`)**: Paired `RedditMarketAgent` with `YahooFinanceAgent` to link social chatter to EOD stock prices.
- **Chapter 4 — Social Expansion & FinBERT (`PR #3`)**: Added StockTwits and Bluesky agents, integrated **FinBERT** (`ProsusAI/finbert`) as a financial-slang anchor, and built a unified CLI.
- **Chapter 5 — Global Press & Testing: GDELT (`PR #5`)**: Added **GDELT DOC 2.0** global news intelligence and automated unit tests (`tests/test_gdelt_agent.py`).
- **Chapter 6 — Orchestration, Supabase & Web Terminal (`PR #6`)**: Unified all 8 agents under `PulseIngestionOrchestrator`, connected **Supabase** (PostgreSQL + RLS), and built the **Next.js** terminal.
- **Chapter 7 — Cloud Polish & Math Calibration**: Added **LangSmith** tracing, **Vercel** serverless service bindings (`vercel.json`), `pulse_snapshot.json` instant-load cache, **252 trading days** of history, and **exponential time-decay** weighting.
- **Chapter 8 — Live Supabase Loading & User-Controlled Freshness**: Switched the frontend loader to query **Supabase PostgreSQL first** on startup, added a clear **`Data last updated on: <date & time>`** indicator, and built a **1-hour staleness notification banner** allowing users to either trigger a fresh scan or keep viewing the current snapshot immediately.
