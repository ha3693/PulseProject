import fs from 'fs'
import path from 'path'
import { createClient } from '@/lib/supabase/server'

export const DEFAULT_WATCHLIST_ITEMS = [
  { slug: 'nvda', notes: 'Core AI infrastructure holding — monitoring Blackwell ramp & options flow' },
  { slug: 'aapl', notes: 'Watching consumer upgrade cycle sentiment vs. services growth' },
  { slug: 'btc-usd', notes: 'Macro liquidity proxy & institutional ETF inflow tracker' },
  { slug: 'nike', notes: 'Brand turnaround tracking vs. Adidas share-of-voice' },
]

function buildAssetsFromSupabase(
  topicRows: any[],
  signalRows: any[],
  priceRows: any[],
  contentRows: any[],
  fallbackAssets: any[]
) {
  const fallbackBySlug = new Map<string, any>(
    (fallbackAssets || []).map((a: any) => [a?.topic?.slug, a])
  )

  const signalsByTopic = new Map<string, any[]>()
  for (const s of signalRows || []) {
    const list = signalsByTopic.get(s.topic_id) || []
    list.push(s)
    signalsByTopic.set(s.topic_id, list)
  }

  const pricesByTopic = new Map<string, any[]>()
  for (const p of priceRows || []) {
    const list = pricesByTopic.get(p.topic_id) || []
    list.push(p)
    pricesByTopic.set(p.topic_id, list)
  }

  const postsByTopic = new Map<string, any[]>()
  for (const c of contentRows || []) {
    const list = postsByTopic.get(c.topic_id) || []
    list.push(c)
    postsByTopic.set(c.topic_id, list)
  }

  const rebuilt: any[] = []

  for (const t of topicRows) {
    const fb = fallbackBySlug.get(t.slug)
    const tSignals = signalsByTopic.get(t.id) || []
    const tPrices = pricesByTopic.get(t.id) || []
    const tPosts = postsByTopic.get(t.id) || []

    // Map prices by date for fast join with daily signals
    const priceByDate = new Map<string, any>()
    for (const p of tPrices) {
      priceByDate.set(String(p.price_date), p)
    }

    const dbHistory: any[] = []
    for (const s of tSignals) {
      const dt = String(s.signal_date)
      const p = priceByDate.get(dt)
      const closePrice = p ? Number(p.close_price) : 0
      const dailyRet = p ? Number(p.daily_return || 0) : 0
      const pulseIdx = Number(s.pulse_index || 0)
      const fbIdx = Number(s.top_drivers?.finbert_index ?? pulseIdx)

      dbHistory.push({
        date: dt,
        open_price: p ? Number(p.open_price ?? closePrice) : closePrice,
        close_price: closePrice,
        high_price: p ? Number(p.high_price ?? closePrice) : closePrice,
        low_price: p ? Number(p.low_price ?? closePrice) : closePrice,
        volume: p ? Number(p.volume || 0) : 0,
        daily_return: dailyRet,
        change_pct: Number((dailyRet * 100).toFixed(2)),
        pulse_index: pulseIdx,
        finbert_index: fbIdx,
        positive_count: Number(s.positive_count || 0),
        neutral_count: Number(s.neutral_count || 0),
        negative_count: Number(s.negative_count || 0),
        total_volume: Number(s.total_volume || 0),
        divergence_flag: Boolean(s.divergence_flag),
        divergence_type: s.divergence_flag
          ? pulseIdx >= 0
            ? 'bullish_divergence'
            : 'bearish_divergence'
          : null,
      })
    }

    // If Supabase has no signals yet for this topic, fall back to snapshot item if present
    if (dbHistory.length === 0) {
      if (fb) rebuilt.push(fb)
      continue
    }

    // Merge older historical bars from snapshot before earliest DB signal date (for 1Y 252D chart)
    const earliestDbDate = dbHistory[0].date
    const olderFbHistory = (fb?.history || []).filter((h: any) => h.date < earliestDbDate)
    const mergedHistory = [...olderFbHistory, ...dbHistory]

    const latestSig = tSignals[tSignals.length - 1]
    const latestHist = mergedHistory[mergedHistory.length - 1]
    const prevHist = mergedHistory.length > 1 ? mergedHistory[mergedHistory.length - 2] : latestHist
    const latestPrice = latestHist.close_price || fb?.latest_price || 0
    const prevPrice = prevHist?.close_price || latestPrice
    const priceChange = Number((latestPrice - prevPrice).toFixed(2))
    const priceChangePct =
      prevPrice > 0 ? Number((((latestPrice - prevPrice) / prevPrice) * 100).toFixed(2)) : 0

    const mappedPosts =
      tPosts.length > 0
        ? tPosts.map((c: any) => {
            const si = Array.isArray(c.sentiment_items) ? c.sentiment_items[0] : c.sentiment_items
            const sScore = Number(si?.sentiment_score ?? 0)
            return {
              external_id: c.external_id || c.id,
              source: c.source,
              outlet: c.source,
              title: c.title || '',
              content_text: c.content_text || c.title || '',
              url: c.url || '',
              published_at: c.published_at,
              engagement_count: Number(c.engagement_count || 0),
              sentiment_label: (si?.sentiment_label || 'neutral') as 'positive' | 'neutral' | 'negative',
              sentiment_score: sScore,
              confidence: Number(si?.confidence ?? 0.85),
              finbert_label: si?.sentiment_label || 'neutral',
              finbert_score: sScore,
              theme_tags: si?.theme_tags || [],
            }
          })
        : fb?.posts || []

    const topDrivers = latestSig.top_drivers || fb?.top_drivers || {
      agent_scores: {},
      finbert_index: Number(latestSig.pulse_index || 0),
      model_agreement_pct: 85,
      positive_catalysts: [],
      risk_factors: [],
      top_themes: [],
      sector: fb?.topic?.sector || 'Market Asset',
    }

    rebuilt.push({
      topic: {
        slug: t.slug,
        name: t.name,
        ticker: t.ticker,
        category: t.category,
        sector: topDrivers.sector || fb?.topic?.sector || 'Market Asset',
        competitor_slugs: t.competitor_slugs || fb?.topic?.competitor_slugs || [],
      },
      pulse_index: Number(latestSig.pulse_index || 0),
      finbert_index: Number(topDrivers.finbert_index ?? latestSig.pulse_index ?? 0),
      latest_price: latestPrice,
      price_change: priceChange,
      price_change_pct: priceChangePct,
      positive_count: Number(latestSig.positive_count || 0),
      neutral_count: Number(latestSig.neutral_count || 0),
      negative_count: Number(latestSig.negative_count || 0),
      total_volume: Number(latestSig.total_volume || 0),
      divergence_flag: Boolean(latestSig.divergence_flag),
      divergence_type: latestHist.divergence_type,
      synthesis: latestSig.summary_text || fb?.synthesis || '',
      top_drivers: topDrivers,
      posts: mappedPosts,
      history: mergedHistory,
    })
  }

  // Preserve canonical ordering from fallbackAssets when available
  if (fallbackAssets?.length) {
    const order = new Map<string, number>(fallbackAssets.map((a: any, i: number) => [a?.topic?.slug, i]))
    rebuilt.sort((a, b) => (order.get(a.topic.slug) ?? 999) - (order.get(b.topic.slug) ?? 999))
  }

  return rebuilt
}

export async function loadPulseTerminalData() {
  const snapshotPath = path.join(process.cwd(), 'lib', 'data', 'pulse_snapshot.json')
  let fallbackSnapshot: any = {
    generated_at: new Date().toISOString(),
    schedule_cron: '0 */6 * * *',
    data_source: 'snapshot_fallback',
    assets: [],
    social_radar: [],
  }

  if (fs.existsSync(snapshotPath)) {
    try {
      fallbackSnapshot = {
        ...JSON.parse(fs.readFileSync(snapshotPath, 'utf-8')),
        data_source: 'snapshot_fallback',
      }
    } catch {
      // Fallback
    }
  }

  let snapshot = fallbackSnapshot
  let user: any = null
  let runs: any[] = []
  let isRefreshing = false
  let watchlistItems: Array<{ slug: string; notes: string }> = [...DEFAULT_WATCHLIST_ITEMS]
  let watchlistSlugs: string[] = DEFAULT_WATCHLIST_ITEMS.map((i) => i.slug)

  try {
    const supabase = await createClient()

    const [
      authRes,
      runsRes,
      topicsRes,
      signalsRes,
      pricesRes,
      contentRes,
    ] = await Promise.all([
      supabase.auth.getUser(),
      supabase
        .from('scheduled_ingestion_runs')
        .select('*')
        .order('started_at', { ascending: false })
        .limit(15),
      supabase
        .from('topics')
        .select('id, slug, name, category, ticker, competitor_slugs, is_active')
        .eq('is_active', true),
      supabase
        .from('daily_sentiment_signals')
        .select('topic_id, signal_date, pulse_index, positive_count, neutral_count, negative_count, total_volume, summary_text, top_drivers, divergence_flag, created_at')
        .order('signal_date', { ascending: true }),
      supabase
        .from('asset_prices')
        .select('topic_id, price_date, open_price, close_price, high_price, low_price, volume, daily_return')
        .order('price_date', { ascending: true }),
      supabase
        .from('raw_content')
        .select('id, topic_id, source, external_id, url, title, content_text, published_at, engagement_count, sentiment_items(sentiment_label, confidence, sentiment_score, theme_tags)')
        .order('published_at', { ascending: false })
        .limit(400),
    ])

    user = authRes?.data?.user || null
    const runRows = runsRes?.data || []
    if (runRows.length > 0) {
      runs = runRows
      const latestReal = runRows.find(
        (r: any) => !Array.isArray(r?.agents_invoked) || !r.agents_invoked.includes('pg_cron_rollup')
      )
      if (
        latestReal &&
        latestReal.status === 'running' &&
        Date.now() - new Date(latestReal.started_at || latestReal.completed_at).getTime() < 4 * 60 * 1000
      ) {
        isRefreshing = true
      }
    }

    const topicRows = topicsRes?.data || []
    const signalRows = signalsRes?.data || []
    const priceRows = pricesRes?.data || []
    const contentRows = contentRes?.data || []

    if (topicRows.length > 0 && signalRows.length > 0) {
      // Find the latest *real* multi-agent ingestion run (ignore pg_cron_rollup health checks)
      const latestRealRun = runRows.find(
        (r: any) =>
          Array.isArray(r.agents_invoked) &&
          !r.agents_invoked.includes('pg_cron_rollup') &&
          Number(r.posts_ingested || 0) > 0
      )

      const maxSignalCreatedAt = signalRows.reduce((max: string, s: any) => {
        const ts = s.created_at ? String(s.created_at) : ''
        return ts > max ? ts : max
      }, '')

      const latestDbTimestamp =
        latestRealRun?.completed_at ||
        maxSignalCreatedAt ||
        fallbackSnapshot.generated_at

      const dbDateMs = new Date(latestDbTimestamp).getTime()
      const fbDateMs = new Date(fallbackSnapshot.generated_at).getTime()

      // Only prefer Supabase over the local snapshot if Supabase is at least as fresh
      if (Number.isNaN(fbDateMs) || dbDateMs >= fbDateMs) {
        const dbAssets = buildAssetsFromSupabase(
          topicRows,
          signalRows,
          priceRows,
          contentRows,
          fallbackSnapshot.assets || []
        )

        if (dbAssets.length > 0) {
          snapshot = {
            ...fallbackSnapshot,
            generated_at: latestDbTimestamp,
            data_source: 'supabase',
            assets: dbAssets,
          }
        }
      }
    }

    if (user) {
      const { data: wlRows } = await supabase
        .from('user_watchlists')
        .select('id, notes, created_at, topic:topics(slug)')
        .eq('user_id', user.id)
        .order('created_at', { ascending: true })

      if (wlRows) {
        watchlistItems = wlRows
          .map((r: any) => ({
            slug: r.topic?.slug,
            notes: r.notes || 'Monitoring daily sentiment vs. price action',
          }))
          .filter((r: any) => Boolean(r.slug))
        watchlistSlugs = watchlistItems.map((i) => i.slug)
      }
    }
  } catch {
    // Graceful fallback to local snapshot if offline
  }

  return {
    snapshot,
    runs,
    isRefreshing,
    watchlistSlugs,
    watchlistItems,
    user,
  }
}
