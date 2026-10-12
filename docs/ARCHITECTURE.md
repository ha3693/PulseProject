# Pulse Architecture & Technical Overview

## 1. System Vision & Objective
Pulse is a real-time sentiment and market signal platform that ingests news and social data across 4–6 public English-language channels, extracts sentiment and key themes using LLMs (benchmarked against FinBERT), and generates a unified **Pulse Sentiment Index** (-100 to +100). 

It pairs this sentiment with asset prices to provide actionable signals across two dedicated lenses:
- **Market Lens**: Divergence tracking, sentiment vs. price trend charts, multi-asset watchlist, and next-day price direction backtesting.
- **Brand Lens**: Praise vs. complaint breakdown, top drivers with source citations, and competitor share-of-voice comparison.

---

## 2. High-Level Architecture Diagram

```
+--------------------------------------------------------------------------+
|                            Data Sources                                  |
|  - News: GDELT DOC 2.0 API, Finnhub / NewsAPI Free Tier                  |
|  - Social: Reddit API (r/investing, r/stocks, r/wsb), Bluesky, StockTwits |
|  - Prices: Yahoo Finance (yfinance) / Alpha Vantage                      |
+------------------------------------+-------------------------------------+
                                     | (Scheduled / Daily ingestion)
                                     v
+--------------------------------------------------------------------------+
|                      Python Data Pipeline (Services)                     |
|  1. Ingestion & Filtering: Deduplication, spam removal, disambiguation   |
|  2. NLP Scoring: LLM (Gemini / Claude / GPT) + FinBERT benchmark         |
|  3. Aggregation Engine: Recency & credibility weighted index (-100..+100)|
|  4. Backtesting Module: Correlation & next-day price direction accuracy  |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                       Storage & Caching (Supabase)                       |
|  - PostgreSQL Database (Raw posts, sentiment scores, daily signals)       |
|  - Auth & Row-Level Security                                             |
|  - Scheduled Cron Triggers & Database Webhooks                           |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                         Frontend Application                             |
|  - Framework: Next.js (App Router) + React                               |
|  - Data Visualization: Recharts (Sentiment-Price overlay, source splits) |
|  - Views: Market Lens, Brand Lens, Historical Backtests, Watchlist       |
+--------------------------------------------------------------------------+
```

---

## 3. Core Algorithms & Methodologies

### 3.1 Sentiment Index Formula
The aggregated Pulse Index $S_{topic, t}$ for a given time window $t$ maps into $[-100, +100]$:
$$S = \frac{\sum_{i} w_{i} \cdot \text{score}_{i}}{\sum_{i} w_{i}}$$
Where:
- $\text{score}_i \in [-100, +100]$ is the calibrated sentiment output of article/post $i$.
- $w_i = r_i \times c_i$ is the item weight.
- $r_i$ is the time-decay recency factor: $r_i = e^{-\lambda \Delta t}$.
- $c_i$ is the source credibility weight (e.g., major financial outlets weighted higher than anonymous social posts).

### 3.2 Market Lens Divergence Detection
A signal divergence occurs when price and sentiment move in opposite directions over a rolling multi-day window:
- **Bullish Divergence**: Price moves downward/sideways while Sentiment Index trends sharply upward.
- **Bearish Divergence**: Price reaches higher highs while Sentiment Index drops substantially.

### 3.3 FinBERT Benchmark & Human Validation
- **Benchmark Corpus**: Hand-labeled set of ~200 real posts across tech stocks and crypto.
- **Evaluation Targets**: $\ge 75\text{--}80\%$ alignment with hand-labeled ground truth.
- FinBERT serves as a deterministic financial-domain baseline to ensure LLM prompts minimize hallucinations and properly handle financial slang (e.g. "bear trap", "short squeeze", "bag holding").
