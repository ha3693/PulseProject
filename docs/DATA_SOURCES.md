# Data Sources and API Integrations

Pulse strictly uses official public APIs and open data. No unauthenticated scraping against site terms is permitted.

---

## 1. News Sources
| Source | Access Type | Rate Limits / Terms | Purpose |
| :--- | :--- | :--- | :--- |
| **GDELT DOC 2.0 API** | Free, Public | Generous public endpoints | Broad global news monitoring and narrative shifts |
| **Finnhub** | Free Tier API | 60 calls/minute | High-credibility financial news feeds and market events |
| **NewsAPI** | Free Developer Tier | 100 requests/day | Supplementary English-language top business headlines |

---

## 2. Social Media Sources
| Source | Access Type | Endpoint / Notes | Purpose |
| :--- | :--- | :--- | :--- |
| **Reddit API** | Official Developer API | PRAW / OAuth (`r/investing`, `r/stocks`, `r/wallstreetbets`) | Retail sentiment, slang, emerging retail trends |
| **StockTwits** | Official Public REST API | Free tier (`/streams/symbol/{id}.json`) | Direct retail investor sentiment tags ($Bullish / $Bearish) |
| **Bluesky (AT Protocol)** | Free Public API | `public.api.bsky.app` | Open, conversational microblogging sentiment |
| **X (Twitter)** *(Stretch)* | Pay-per-use API | Budget-capped ($100 basic tier) | Extended social reach if project budget permits |

---

## 3. Market Pricing Data
| Asset Class | Primary Provider | Tool / Library | Frequency |
| :--- | :--- | :--- | :--- |
| **US Equities** (10 Tech) | Yahoo Finance / Alpha Vantage | `yfinance` in Python | Daily EOD OHLCV |
| **Commodities** (Gold) | Yahoo Finance (`GC=F`) | `yfinance` | Daily EOD OHLCV |
| **Crypto** (Bitcoin) | Yahoo Finance (`BTC-USD`) | `yfinance` | Daily EOD OHLCV |

---

## 4. Benchmark & Training Datasets
- **Financial PhraseBank** (Malo et al. / Hugging Face)
- **FiQA Financial Opinion Mining** (Hugging Face)
- **Hand-Labeled Verification Set**: 200 manually curated, domain-specific posts from Reddit/News for testing model agreement with FinBERT and LLMs.

---

## 5. Data Privacy & Compliance Policy
1. **No Personal Identifiable Information (PII)**: We store only post text, publication timestamps, source identifiers, and engagement counts (e.g. upvotes, comment volume). Author handles and personal profile data are never stored or tracked.
2. **Caching Policy**: Data is refreshed on a daily schedule, scored once upon ingestion, and cached in Supabase to minimize LLM compute overhead and API rate limits.
3. **Public Analytical Signal**: Outputs are informational signals for research and education, not financial or investment advice.
