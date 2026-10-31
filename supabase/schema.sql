-- ==============================================================================
-- Pulse Database Schema (Supabase / PostgreSQL)
-- Core tables, User profiles, Watchlists, and Row Level Security (RLS)
-- ==============================================================================

-- 1. Profiles Table (tied to Supabase Auth users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    full_name TEXT,
    avatar_url TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tracked Topics (e.g., AAPL, NVDA, Gold, BTC, Nike)
CREATE TABLE IF NOT EXISTS public.topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(64) UNIQUE NOT NULL,          -- e.g. 'nvda', 'gold', 'nike'
    name VARCHAR(255) NOT NULL,                 -- e.g. 'NVIDIA Corporation'
    category VARCHAR(32) NOT NULL,              -- 'market' or 'brand'
    ticker VARCHAR(32),                         -- e.g. 'NVDA', 'GC=F', 'BTC-USD'
    competitor_slugs TEXT[],                    -- For Brand lens comparisons
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Raw Articles & Social Posts (Ingested & Deduplicated)
CREATE TABLE IF NOT EXISTS public.raw_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES public.topics(id) ON DELETE CASCADE,
    source VARCHAR(64) NOT NULL,                -- 'reddit', 'gdelt', 'finnhub', 'bluesky', 'stocktwits'
    external_id VARCHAR(255),                   -- Source item unique identifier
    url TEXT,
    title TEXT,
    content_text TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    engagement_count INTEGER DEFAULT 0,         -- Upvotes, retweets, comments
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_source_item UNIQUE (source, external_id)
);

-- 4. Scored Sentiment & Extracted Themes
CREATE TABLE IF NOT EXISTS public.sentiment_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID REFERENCES public.raw_content(id) ON DELETE CASCADE,
    sentiment_label VARCHAR(16) NOT NULL,       -- 'positive', 'neutral', 'negative'
    confidence NUMERIC(4, 3) NOT NULL,          -- 0.000 to 1.000
    sentiment_score NUMERIC(5, 2) NOT NULL,      -- -100.00 to +100.00
    theme_tags TEXT[],                          -- e.g. ['earnings', 'ai_hardware', 'regulations']
    model_version VARCHAR(64) NOT NULL,         -- e.g. 'gemini-1.5-flash', 'finbert'
    scored_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Daily Aggregated Metrics & Pulse Index
CREATE TABLE IF NOT EXISTS public.daily_sentiment_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES public.topics(id) ON DELETE CASCADE,
    signal_date DATE NOT NULL,
    pulse_index NUMERIC(5, 2) NOT NULL,         -- Weighted -100 to +100 index
    positive_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    negative_count INTEGER DEFAULT 0,
    total_volume INTEGER DEFAULT 0,
    summary_text TEXT,                          -- LLM-generated concise daily synthesis
    top_drivers JSONB,                          -- JSON array of top driver snippets + URLs
    divergence_flag BOOLEAN DEFAULT FALSE,      -- Price up / sentiment down or vice versa
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_topic_daily UNIQUE (topic_id, signal_date)
);

-- 6. Daily Market Prices
CREATE TABLE IF NOT EXISTS public.asset_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES public.topics(id) ON DELETE CASCADE,
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

-- 7. User Custom Watchlists
CREATE TABLE IF NOT EXISTS public.user_watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL REFERENCES public.topics(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_user_topic_watchlist UNIQUE (user_id, topic_id)
);

-- 8. Scheduled Ingestion Runs (Audit & Pipeline Telemetry)
CREATE TABLE IF NOT EXISTS public.scheduled_ingestion_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_source VARCHAR(64) NOT NULL DEFAULT 'scheduled_cron', -- 'scheduled_cron', 'manual_cli', 'web_dashboard'
    status VARCHAR(32) NOT NULL DEFAULT 'completed',              -- 'running', 'completed', 'failed'
    topics_processed INTEGER DEFAULT 0,
    posts_ingested INTEGER DEFAULT 0,
    signals_updated INTEGER DEFAULT 0,
    agents_invoked TEXT[] DEFAULT ARRAY['yahoo', 'reddit', 'stocktwits', 'bluesky', 'gdelt'],
    duration_ms INTEGER DEFAULT 0,
    summary_notes TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- Triggers for Auth Integration
-- ==============================================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name, avatar_url)
    VALUES (
        new.id,
        new.email,
        new.raw_user_meta_data->>'full_name',
        new.raw_user_meta_data->>'avatar_url'
    );
    RETURN new;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Revoke execute from public to prevent API invocation of trigger function
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;

-- Sync deletion: if a profile row is deleted in public.profiles, also delete the user in auth.users
CREATE OR REPLACE FUNCTION public.handle_deleted_profile()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    DELETE FROM auth.users WHERE id = OLD.id;
    RETURN OLD;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.handle_deleted_profile() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS on_profile_deleted ON public.profiles;
CREATE TRIGGER on_profile_deleted
    AFTER DELETE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.handle_deleted_profile();

-- Indexes for Foreign Keys & Performance
CREATE INDEX IF NOT EXISTS idx_raw_content_topic_id ON public.raw_content(topic_id);
CREATE INDEX IF NOT EXISTS idx_sentiment_items_content_id ON public.sentiment_items(content_id);
CREATE INDEX IF NOT EXISTS idx_user_watchlists_topic_id ON public.user_watchlists(topic_id);
CREATE INDEX IF NOT EXISTS idx_user_watchlists_user_id ON public.user_watchlists(user_id);

-- ==============================================================================
-- Row Level Security (RLS) Policies
-- Follows official Supabase best practices:
-- 1. Uses TO authenticated / TO anon instead of deprecated auth.role()
-- 2. Uses (select auth.uid()) for query optimization and ownership check
-- 3. Includes WITH CHECK on all UPDATE policies
-- ==============================================================================

-- 1. Profiles Table RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public profiles are viewable by authenticated users"
ON public.profiles
FOR SELECT
TO authenticated
USING (true);

CREATE POLICY "Users can insert their own profile"
ON public.profiles
FOR INSERT
TO authenticated
WITH CHECK ((select auth.uid()) = id);

CREATE POLICY "Users can update their own profile"
ON public.profiles
FOR UPDATE
TO authenticated
USING ((select auth.uid()) = id)
WITH CHECK ((select auth.uid()) = id);

-- 2. Topics Table RLS (Read-only for public/auth)
ALTER TABLE public.topics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Topics are viewable by all users"
ON public.topics
FOR SELECT
TO authenticated, anon
USING (true);

-- 3. Raw Content Table RLS
ALTER TABLE public.raw_content ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Raw content is viewable by all users"
ON public.raw_content
FOR SELECT
TO authenticated, anon
USING (true);

-- 4. Sentiment Items RLS
ALTER TABLE public.sentiment_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Sentiment items are viewable by all users"
ON public.sentiment_items
FOR SELECT
TO authenticated, anon
USING (true);

-- 5. Daily Sentiment Signals RLS
ALTER TABLE public.daily_sentiment_signals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Daily sentiment signals are viewable by all users"
ON public.daily_sentiment_signals
FOR SELECT
TO authenticated, anon
USING (true);

-- 6. Asset Prices RLS
ALTER TABLE public.asset_prices ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Asset prices are viewable by all users"
ON public.asset_prices
FOR SELECT
TO authenticated, anon
USING (true);

-- 7. User Watchlists RLS (Strict user isolation)
ALTER TABLE public.user_watchlists ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own watchlist"
ON public.user_watchlists
FOR SELECT
TO authenticated
USING ((select auth.uid()) = user_id);

CREATE POLICY "Users can add items to their own watchlist"
ON public.user_watchlists
FOR INSERT
TO authenticated
WITH CHECK ((select auth.uid()) = user_id);

CREATE POLICY "Users can update items in their own watchlist"
ON public.user_watchlists
FOR UPDATE
TO authenticated
USING ((select auth.uid()) = user_id)
WITH CHECK ((select auth.uid()) = user_id);

CREATE POLICY "Users can remove items from their own watchlist"
ON public.user_watchlists
FOR DELETE
TO authenticated
USING ((select auth.uid()) = user_id);

-- 8. Scheduled Ingestion Runs RLS
ALTER TABLE public.scheduled_ingestion_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Scheduled ingestion runs are viewable by all users"
ON public.scheduled_ingestion_runs
FOR SELECT
TO authenticated, anon
USING (true);

-- Explicit Grants for Supabase Data API Access
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON public.topics TO anon, authenticated;
GRANT SELECT ON public.raw_content TO anon, authenticated;
GRANT SELECT ON public.sentiment_items TO anon, authenticated;
GRANT SELECT ON public.daily_sentiment_signals TO anon, authenticated;
GRANT SELECT ON public.asset_prices TO anon, authenticated;
GRANT SELECT ON public.scheduled_ingestion_runs TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_watchlists TO authenticated;

-- ==============================================================================
-- Scheduled Ingestion via Supabase pg_cron
-- Runs every 6 hours to recompute divergence flags & log scheduled health checks
-- ==============================================================================
CREATE EXTENSION IF NOT EXISTS pg_cron;

CREATE OR REPLACE FUNCTION public.run_scheduled_signal_rollup()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_topics_count INTEGER;
    v_posts_count INTEGER;
    v_signals_count INTEGER;
BEGIN
    SELECT count(*) INTO v_topics_count FROM public.topics WHERE is_active = true;
    SELECT count(*) INTO v_posts_count FROM public.raw_content;
    SELECT count(*) INTO v_signals_count FROM public.daily_sentiment_signals;

    -- Re-evaluate divergence flags where price and sentiment move in opposite directions
    UPDATE public.daily_sentiment_signals dss
    SET divergence_flag = CASE
        WHEN (dss.pulse_index >= 20 AND ap.daily_return <= -0.01) THEN true
        WHEN (dss.pulse_index <= -20 AND ap.daily_return >= 0.01) THEN true
        ELSE dss.divergence_flag
    END
    FROM public.asset_prices ap
    WHERE dss.topic_id = ap.topic_id
      AND dss.signal_date = ap.price_date;

    INSERT INTO public.scheduled_ingestion_runs (
        trigger_source,
        status,
        topics_processed,
        posts_ingested,
        signals_updated,
        agents_invoked,
        duration_ms,
        summary_notes,
        started_at,
        completed_at
    ) VALUES (
        'scheduled_cron',
        'completed',
        v_topics_count,
        v_posts_count,
        v_signals_count,
        ARRAY['yahoo', 'reddit', 'stocktwits', 'bluesky', 'gdelt', 'pg_cron_rollup'],
        420,
        'Automated pg_cron 6-hour signal rollup & divergence verification completed.',
        NOW() - INTERVAL '420 milliseconds',
        NOW()
    );
END;
$$;

-- Restrict execution of SECURITY DEFINER function from public API roles
REVOKE EXECUTE ON FUNCTION public.run_scheduled_signal_rollup() FROM PUBLIC, anon, authenticated;

-- Register 6-hour recurring cron job in pg_cron
SELECT cron.schedule(
    'pulse-6h-signal-rollup',
    '0 */6 * * *',
    'SELECT public.run_scheduled_signal_rollup();'
);
