-- Schema Draft for Pulse Database (Supabase / PostgreSQL)
-- For review and team alignment

-- 1. Tracked Topics (e.g., AAPL, NVDA, Gold, BTC, Nike)
CREATE TABLE IF NOT EXISTS topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(64) UNIQUE NOT NULL,          -- e.g. 'nvda', 'gold', 'nike'
    name VARCHAR(255) NOT NULL,                 -- e.g. 'NVIDIA Corporation'
    category VARCHAR(32) NOT NULL,              -- 'market' or 'brand'
    ticker VARCHAR(32),                         -- e.g. 'NVDA', 'GC=F', 'BTC-USD'
    competitor_slugs TEXT[],                    -- For Brand lens comparisons
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Raw Articles & Social Posts (Ingested & Deduplicated)
CREATE TABLE IF NOT EXISTS raw_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    source VARCHAR(64) NOT NULL,                -- 'reddit', 'gdelt', 'finnhub', 'bluesky', 'stocktwits'
    external_id VARCHAR(255),                   -- Source item unique identifier
    url TEXT,
    title TEXT,
    content_text TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    engagement_count INTEGER DEFAULT 0,         -- Upvotes, retweets, comments (no personal profile data)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_source_item UNIQUE (source, external_id)
);

-- 3. Scored Sentiment & Extracted Themes
CREATE TABLE IF NOT EXISTS sentiment_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID REFERENCES raw_content(id) ON DELETE CASCADE,
    sentiment_label VARCHAR(16) NOT NULL,       -- 'positive', 'neutral', 'negative'
    confidence NUMERIC(4, 3) NOT NULL,          -- 0.000 to 1.000
    sentiment_score NUMERIC(5, 2) NOT NULL,      -- -100.00 to +100.00
    theme_tags TEXT[],                          -- e.g. ['earnings', 'ai_hardware', 'regulations']
    model_version VARCHAR(64) NOT NULL,         -- e.g. 'gemini-1.5-flash', 'finbert'
    scored_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Daily Aggregated Metrics & Pulse Index
CREATE TABLE IF NOT EXISTS daily_sentiment_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    signal_date DATE NOT NULL,
    pulse_index NUMERIC(5, 2) NOT NULL,         -- Weighted -100 to +100 index
    positive_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    negative_count INTEGER DEFAULT 0,
    total_volume INTEGER DEFAULT 0,
    summary_text TEXT,                          -- LLM-generated concise daily synthesis
    top_drivers JSONB,                          -- JSON array of top positive/negative driver snippets + URLs
    divergence_flag BOOLEAN DEFAULT FALSE,      -- Price up / sentiment down or vice versa
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_topic_daily UNIQUE (topic_id, signal_date)
);

-- 5. Daily Market Prices (for Market lens correlation & backtesting)
CREATE TABLE IF NOT EXISTS asset_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    price_date DATE NOT NULL,
    open_price NUMERIC(12, 4),
    close_price NUMERIC(12, 4) NOT NULL,
    high_price NUMERIC(12, 4),
    low_price NUMERIC(12, 4),
    volume BIGINT,
    daily_return NUMERIC(8, 5),                 -- (close - prev_close) / prev_close
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_topic_price_date UNIQUE (topic_id, price_date)
);
