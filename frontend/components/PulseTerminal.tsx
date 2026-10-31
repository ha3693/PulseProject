'use client'

import React, { useState, useMemo, useEffect } from 'react'
import { useRouter } from 'next/navigation'

export interface HistoryPoint {
  date: string
  open_price: number
  close_price: number
  high_price: number
  low_price: number
  volume: number
  daily_return: number
  change_pct: number
  pulse_index: number
  finbert_index: number
  positive_count: number
  neutral_count: number
  negative_count: number
  total_volume: number
  divergence_flag: boolean
  divergence_type: string | null
}

export interface IngestedPost {
  external_id: string
  source: string
  outlet: string
  title: string
  content_text: string
  url: string
  published_at: string
  engagement_count: number
  sentiment_label: 'positive' | 'neutral' | 'negative'
  sentiment_score: number
  confidence: number
  finbert_label: string
  finbert_score: number
  theme_tags: string[]
}

export interface AssetSignal {
  topic: {
    slug: string
    name: string
    ticker: string
    category: string
    sector: string
    competitor_slugs: string[]
  }
  pulse_index: number
  finbert_index: number
  latest_price: number
  price_change: number
  price_change_pct: number
  positive_count: number
  neutral_count: number
  negative_count: number
  total_volume: number
  divergence_flag: boolean
  divergence_type: string | null
  synthesis: string
  top_drivers: {
    agent_scores: Record<string, number>
    finbert_index: number
    model_agreement_pct: number
    positive_catalysts: string[]
    risk_factors: string[]
    top_themes: string[]
    sector: string
  }
  posts: IngestedPost[]
  history: HistoryPoint[]
}

export interface SocialRadarItem {
  platform: string
  handle: string
  role: string
  sentiment_signal: string
  posts_analyzed: number
  key_themes: string[]
  milestones: string[]
  executive_summary: string
  generated_at: string
}

export interface IngestionRunLog {
  id: string
  trigger_source: string
  status: string
  topics_processed: number
  posts_ingested: number
  signals_updated: number
  agents_invoked: string[]
  duration_ms: number
  summary_notes: string
  started_at: string
  completed_at: string
}

interface PulseTerminalProps {
  initialSnapshot: {
    generated_at: string
    schedule_cron: string
    assets: AssetSignal[]
    social_radar: SocialRadarItem[]
  }
  initialRuns: IngestionRunLog[]
  initialWatchlistSlugs: string[]
  userEmail?: string | null
  initialTab?: 'market' | 'brand' | 'backtest' | 'social' | 'pipeline'
  initialAssetSlug?: string
}

const AGENT_META: Record<string, { label: string; weight: string; color: string; badge: string }> = {
  yahoo: { label: 'Yahoo Finance EOD', weight: '1.35x', color: '#06b6d4', badge: 'INSTITUTIONAL' },
  gdelt: { label: 'GDELT DOC 2.0 News', weight: '1.30x', color: '#3b82f6', badge: 'GLOBAL PRESS' },
  reddit: { label: 'Reddit (r/investing, wsb)', weight: '1.00x', color: '#f97316', badge: 'RETAIL DD' },
  stocktwits: { label: 'StockTwits Stream', weight: '0.95x', color: '#10b981', badge: 'OPTIONS FLOW' },
  bluesky: { label: 'Bluesky Social Pulse', weight: '0.90x', color: '#8b5cf6', badge: 'TECH DISCOURSE' },
}

export default function PulseTerminal({
  initialSnapshot,
  initialRuns,
  initialWatchlistSlugs,
  userEmail,
  initialTab = 'market',
  initialAssetSlug = 'nvda',
}: PulseTerminalProps) {
  const [assets, setAssets] = useState<AssetSignal[]>(initialSnapshot?.assets || [])
  const [socialRadar, setSocialRadar] = useState<SocialRadarItem[]>(initialSnapshot?.social_radar || [])
  const [runs, setRuns] = useState<IngestionRunLog[]>(initialRuns || [])
  const [lastUpdated, setLastUpdated] = useState<string>(initialSnapshot?.generated_at || new Date().toISOString())

  const [activeTab, setActiveTab] = useState<'market' | 'brand' | 'backtest' | 'social' | 'pipeline'>(initialTab)
  const [selectedSlug, setSelectedSlug] = useState<string>(initialAssetSlug)
  const [compareSlug, setCompareSlug] = useState<string>('adidas')
  const [brandPrimarySlug, setBrandPrimarySlug] = useState<string>('nike')

  // Chart & Feed Filters
  const [chartWindow, setChartWindow] = useState<7 | 14 | 30>(30)
  const [showFinbertOverlay, setShowFinbertOverlay] = useState<boolean>(true)
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  const [sentimentFilter, setSentimentFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')

  // Backtesting interactive controls
  const [btThreshold, setBtThreshold] = useState<number>(18)
  const [btHorizon, setBtHorizon] = useState<1 | 3>(1)

  // Watchlist & Live Ingestion state
  const router = useRouter()
  const [watchlist, setWatchlist] = useState<string[]>(initialWatchlistSlugs || ['nvda', 'aapl', 'btc-usd', 'nike'])
  const [watchlistToast, setWatchlistToast] = useState<string | null>(null)
  const [isIngesting, setIsIngesting] = useState<boolean>(false)
  const [ingestStatusMsg, setIngestStatusMsg] = useState<string | null>(null)

  useEffect(() => {
    if (initialWatchlistSlugs) {
      setWatchlist(initialWatchlistSlugs)
    }
  }, [initialWatchlistSlugs])

  useEffect(() => {
    let active = true
    async function syncWatchlist() {
      try {
        const res = await fetch('/api/watchlist', { cache: 'no-store' })
        if (!res.ok) return
        const data = await res.json()
        if (active && data?.authenticated && Array.isArray(data.items)) {
          const slugs = data.items.map((item: any) => item.topic?.slug).filter(Boolean)
          setWatchlist(slugs)
        }
      } catch {
        // Ignore offline errors
      }
    }
    syncWatchlist()
    window.addEventListener('pulse-watchlist-updated', syncWatchlist)
    return () => {
      active = false
      window.removeEventListener('pulse-watchlist-updated', syncWatchlist)
    }
  }, [])

  const currentAsset = useMemo(
    () => assets.find((a) => a.topic.slug === selectedSlug) || assets[0],
    [assets, selectedSlug]
  )

  const filteredAssetsList = useMemo(() => {
    return assets.filter((a) => {
      if (categoryFilter === 'watchlist') return watchlist.includes(a.topic.slug)
      if (categoryFilter === 'divergences') {
        return a.divergence_flag || a.history.slice(-7).some((h) => h.divergence_flag)
      }
      if (categoryFilter !== 'all' && a.topic.category !== categoryFilter) return false
      return true
    })
  }, [assets, categoryFilter, watchlist])

  const chartHistory = useMemo(() => {
    if (!currentAsset) return []
    return currentAsset.history.slice(-chartWindow)
  }, [currentAsset, chartWindow])

  const filteredPosts = useMemo(() => {
    if (!currentAsset) return []
    return currentAsset.posts.filter((p) => {
      if (sourceFilter !== 'all' && p.source !== sourceFilter) return false
      if (sentimentFilter !== 'all' && p.sentiment_label !== sentimentFilter) return false
      if (
        searchQuery.trim() &&
        !p.title.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !p.outlet.toLowerCase().includes(searchQuery.toLowerCase())
      ) {
        return false
      }
      return true
    })
  }, [currentAsset, sourceFilter, sentimentFilter, searchQuery])

  // Brand Lens pair
  const primaryBrand = useMemo(
    () => assets.find((a) => a.topic.slug === brandPrimarySlug) || assets.find((a) => a.topic.slug === 'nike') || assets[0],
    [assets, brandPrimarySlug]
  )
  const competitorBrand = useMemo(
    () => assets.find((a) => a.topic.slug === compareSlug) || assets.find((a) => a.topic.slug === 'adidas') || assets[1],
    [assets, compareSlug]
  )

  // Backtesting calculations
  const backtestStats = useMemo(() => {
    if (!currentAsset) return null
    const hist = currentAsset.history
    const trades: Array<{
      date: string
      pulse_index: number
      direction: 'LONG' | 'SHORT'
      is_divergence: boolean
      entry_price: number
      exit_price: number
      forward_return_pct: number
      correct: boolean
    }> = []

    let strategyEquity = 10000
    let buyHoldEquity = 10000
    const initialPrice = hist[0]?.close_price || 1
    const equitySeries: Array<{ date: string; strategy: number; benchmark: number }> = []

    for (let i = 0; i < hist.length - btHorizon; i++) {
      const bar = hist[i]
      const nextBar = hist[i + btHorizon]
      const fwdRet = (nextBar.close_price - bar.close_price) / bar.close_price
      buyHoldEquity = 10000 * (nextBar.close_price / initialPrice)

      if (Math.abs(bar.pulse_index) >= btThreshold || bar.divergence_flag) {
        const direction: 'LONG' | 'SHORT' = bar.pulse_index >= 0 ? 'LONG' : 'SHORT'
        const stratRet = direction === 'LONG' ? fwdRet : -fwdRet
        // Apply daily step scaling
        strategyEquity = strategyEquity * (1 + stratRet / btHorizon)
        const correct = (direction === 'LONG' && fwdRet > 0) || (direction === 'SHORT' && fwdRet < 0)

        trades.push({
          date: bar.date,
          pulse_index: bar.pulse_index,
          direction,
          is_divergence: bar.divergence_flag,
          entry_price: bar.close_price,
          exit_price: nextBar.close_price,
          forward_return_pct: Number((fwdRet * 100).toFixed(2)),
          correct,
        })
      }

      equitySeries.push({
        date: nextBar.date,
        strategy: Math.round(strategyEquity),
        benchmark: Math.round(buyHoldEquity),
      })
    }

    const wins = trades.filter((t) => t.correct).length
    const hitRate = trades.length > 0 ? Number(((wins / trades.length) * 100).toFixed(1)) : 0
    const divTrades = trades.filter((t) => t.is_divergence)
    const divWins = divTrades.filter((t) => t.correct).length
    const divHitRate = divTrades.length > 0 ? Number(((divWins / divTrades.length) * 100).toFixed(1)) : 0
    const stratTotalRet = Number((((strategyEquity - 10000) / 10000) * 100).toFixed(2))
    const bhTotalRet = Number((((buyHoldEquity - 10000) / 10000) * 100).toFixed(2))

    return {
      trades: trades.slice().reverse(),
      totalTrades: trades.length,
      wins,
      hitRate,
      divHitRate,
      stratTotalRet,
      bhTotalRet,
      alpha: Number((stratTotalRet - bhTotalRet).toFixed(2)),
      equitySeries,
    }
  }, [currentAsset, btThreshold, btHorizon])

  async function handleToggleWatchlist(slug: string) {
    const exists = watchlist.includes(slug)
    const updated = exists ? watchlist.filter((s) => s !== slug) : [...watchlist, slug]
    setWatchlist(updated)
    setWatchlistToast(exists ? `Removed ${slug.toUpperCase()} from Watchlist` : `Added ${slug.toUpperCase()} to Watchlist`)
    setTimeout(() => setWatchlistToast(null), 3000)

    try {
      if (exists) {
        await fetch(`/api/watchlist?slug=${encodeURIComponent(slug)}`, { method: 'DELETE' })
      } else {
        await fetch('/api/watchlist', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slug }),
        })
      }
      window.dispatchEvent(new CustomEvent('pulse-watchlist-updated'))
      router.refresh()
    } catch {
      // Local state already updated
    }
  }

  async function handleTriggerIngestion(targetTopic?: string) {
    setIsIngesting(true)
    setIngestStatusMsg(
      targetTopic
        ? `Executing Yahoo, Reddit, StockTwits, Bluesky & GDELT agents for ${targetTopic.toUpperCase()}...`
        : 'Executing full multi-agent scheduled ingestion across all 14 topics & syncing to Supabase...'
    )
    try {
      const res = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: targetTopic || 'ALL' }),
      })
      const data = await res.json()
      if (data?.snapshot?.assets) {
        setAssets(data.snapshot.assets)
        setSocialRadar(data.snapshot.social_radar || socialRadar)
        setLastUpdated(data.snapshot.generated_at)
      }
      if (data?.runs) {
        setRuns(data.runs)
      }
      setIngestStatusMsg(
        `✅ Live ingestion complete for ${data.topic || 'all assets'} — synced to Supabase PostgreSQL!`
      )
    } catch (e: any) {
      setIngestStatusMsg(`⚠️ Ingestion notice: ${e?.message || 'Completed using cached snapshot'}`)
    } finally {
      setIsIngesting(false)
      setTimeout(() => setIngestStatusMsg(null), 5000)
    }
  }

  if (!currentAsset) {
    return <div className="container" style={{ padding: '4rem 0' }}>Loading Pulse Intelligence Terminal...</div>
  }

  // Dual-Axis SVG Chart Geometry
  const svgW = 860
  const svgH = 310
  const padL = 54
  const padR = 54
  const padT = 26
  const padB = 36
  const plotW = svgW - padL - padR
  const plotH = svgH - padT - padB

  const prices = chartHistory.map((d) => d.close_price)
  const minP = Math.min(...prices) * 0.985
  const maxP = Math.max(...prices) * 1.015
  const priceRange = Math.max(maxP - minP, 0.01)

  const xCoord = (i: number) =>
    chartHistory.length > 1 ? padL + (i / (chartHistory.length - 1)) * plotW : padL + plotW / 2
  const yPrice = (p: number) => padT + plotH - ((p - minP) / priceRange) * plotH
  const ySent = (s: number) => padT + plotH - ((s + 100) / 200) * plotH

  const pricePath = chartHistory
    .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xCoord(i).toFixed(1)} ${yPrice(d.close_price).toFixed(1)}`)
    .join(' ')
  const priceAreaPath = `${pricePath} L ${xCoord(chartHistory.length - 1).toFixed(1)} ${(padT + plotH).toFixed(1)} L ${xCoord(0).toFixed(1)} ${(padT + plotH).toFixed(1)} Z`
  const sentPath = chartHistory
    .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xCoord(i).toFixed(1)} ${ySent(d.pulse_index).toFixed(1)}`)
    .join(' ')
  const finbertPath = chartHistory
    .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xCoord(i).toFixed(1)} ${ySent(d.finbert_index).toFixed(1)}`)
    .join(' ')

  const activeHoverPoint = hoverIdx !== null && chartHistory[hoverIdx] ? chartHistory[hoverIdx] : chartHistory[chartHistory.length - 1]

  return (
    <div>
      {/* 1. LIVE MARKET TICKER TAPE */}
      <div className="ticker-tape-wrap">
        <div className="container" style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', overflowX: 'auto', padding: '0.55rem 1rem' }}>
          <span className="live-dot-pill">
            <span className="pulse-dot" /> LIVE SIGNALS
          </span>
          {assets.map((item) => {
            const isSelected = item.topic.slug === selectedSlug
            const isBull = item.pulse_index >= 15
            const isBear = item.pulse_index <= -15
            return (
              <button
                key={item.topic.slug}
                onClick={() => {
                  setSelectedSlug(item.topic.slug)
                  if (activeTab !== 'market' && activeTab !== 'backtest') {
                    setActiveTab('market')
                  }
                }}
                className={`ticker-chip ${isSelected ? 'ticker-chip-active' : ''}`}
              >
                <span style={{ fontWeight: 700, color: '#f8fafc' }}>{item.topic.ticker}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: '#cbd5e1' }}>
                  ${item.latest_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.73rem',
                    color: item.price_change_pct >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)',
                  }}
                >
                  {item.price_change_pct >= 0 ? '+' : ''}
                  {item.price_change_pct}%
                </span>
                <span
                  className="terminal-badge"
                  style={{
                    padding: '0.1rem 0.38rem',
                    fontSize: '0.68rem',
                    backgroundColor: isBull
                      ? 'rgba(16, 185, 129, 0.16)'
                      : isBear
                      ? 'rgba(244, 63, 94, 0.16)'
                      : 'rgba(6, 182, 212, 0.14)',
                    color: isBull ? '#34d399' : isBear ? '#fb7185' : '#38bdf8',
                  }}
                >
                  {item.pulse_index >= 0 ? `+${item.pulse_index}` : item.pulse_index}
                </span>
                {item.divergence_flag && (
                  <span title="Price vs. Sentiment Divergence Detected" style={{ color: '#fbbf24', fontSize: '0.75rem' }}>
                    ⚡
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* TOAST BANNERS */}
      {(watchlistToast || ingestStatusMsg) && (
        <div className="container" style={{ marginTop: '1rem' }}>
          <div
            style={{
              padding: '0.75rem 1.25rem',
              borderRadius: '8px',
              background: 'linear-gradient(90deg, rgba(6,182,212,0.18), rgba(16,185,129,0.15))',
              border: '1px solid rgba(6,182,212,0.4)',
              color: '#f8fafc',
              fontSize: '0.88rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>{ingestStatusMsg || watchlistToast}</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
              Supabase RLS Synced
            </span>
          </div>
        </div>
      )}

      {/* 2. TOP COMMAND HEADER & LENS NAVIGATION TABS */}
      <div className="container" style={{ paddingTop: '1.5rem', paddingBottom: '3.5rem' }}>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '1rem',
            marginBottom: '1.5rem',
            paddingBottom: '1.15rem',
            borderBottom: '1px solid var(--border-color)',
          }}
        >
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {[
              { id: 'market', label: '📈 Market Lens', desc: 'Signals & Divergence' },
              { id: 'brand', label: '🏷️ Brand Lens', desc: 'Share of Voice' },
              { id: 'backtest', label: '🧪 Backtesting Lab', desc: 'Next-Day Alpha' },
              { id: 'social', label: '📡 Social Radar', desc: 'Influencer Streams' },
              { id: 'pipeline', label: '⚙️ Scheduled Ingestion', desc: 'pg_cron & Agents' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`lens-tab-btn ${activeTab === tab.id ? 'lens-tab-btn-active' : ''}`}
              >
                <span style={{ fontWeight: 600 }}>{tab.label}</span>
                <span style={{ fontSize: '0.72rem', opacity: 0.75, marginLeft: '0.35rem' }}>{tab.desc}</span>
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Synced: {new Date(lastUpdated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
            <button
              onClick={() => handleTriggerIngestion(currentAsset.topic.ticker)}
              disabled={isIngesting}
              className="btn btn-primary"
              style={{ padding: '0.45rem 0.95rem', fontSize: '0.82rem' }}
            >
              {isIngesting ? '⏳ Running 5 Agents...' : `⚡ Live Scan (${currentAsset.topic.ticker})`}
            </button>
          </div>
        </div>

        {/* ===================================================================
            TAB 1: MARKET LENS
           =================================================================== */}
        {activeTab === 'market' && (
          <div className="terminal-grid-layout">
            {/* LEFT SIDEBAR: ASSET WATCHLIST & SELECTOR */}
            <aside className="card" style={{ padding: '1.1rem', height: 'fit-content' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
                <h3 style={{ fontSize: '0.92rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-secondary)' }}>
                  Tracked Universe ({filteredAssetsList.length})
                </h3>
                <span style={{ fontSize: '0.72rem', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                  5 Agents
                </span>
              </div>

              {/* Filter Pills */}
              <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '0.9rem' }}>
                {[
                  { id: 'all', label: 'All (14)' },
                  { id: 'watchlist', label: `★ Watchlist (${watchlist.length})` },
                  { id: 'divergences', label: '⚡ Divergences' },
                  { id: 'brand', label: 'Brands' },
                ].map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setCategoryFilter(f.id)}
                    style={{
                      padding: '0.25rem 0.55rem',
                      borderRadius: '6px',
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      border: '1px solid',
                      borderColor: categoryFilter === f.id ? 'var(--accent-cyan)' : 'var(--border-color)',
                      backgroundColor: categoryFilter === f.id ? 'rgba(6, 182, 212, 0.16)' : 'transparent',
                      color: categoryFilter === f.id ? '#38bdf8' : 'var(--text-secondary)',
                    }}
                  >
                    {f.label}
                  </button>
                ))}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', maxHeight: '680px', overflowY: 'auto' }}>
                {filteredAssetsList.map((item) => {
                  const active = item.topic.slug === selectedSlug
                  const starred = watchlist.includes(item.topic.slug)
                  const hasDiv = item.divergence_flag || item.history.slice(-5).some((h) => h.divergence_flag)
                  return (
                    <div
                      key={item.topic.slug}
                      onClick={() => setSelectedSlug(item.topic.slug)}
                      style={{
                        padding: '0.7rem 0.8rem',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        border: '1px solid',
                        borderColor: active ? 'var(--accent-cyan)' : 'var(--border-color)',
                        backgroundColor: active ? 'rgba(6, 182, 212, 0.11)' : 'rgba(15, 23, 42, 0.55)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleToggleWatchlist(item.topic.slug)
                            }}
                            style={{
                              background: 'none',
                              border: 'none',
                              cursor: 'pointer',
                              color: starred ? '#fbbf24' : '#475569',
                              fontSize: '0.9rem',
                            }}
                            title="Toggle Watchlist"
                          >
                            ★
                          </button>
                          <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{item.topic.ticker}</span>
                          {hasDiv && (
                            <span
                              style={{
                                fontSize: '0.65rem',
                                padding: '0.05rem 0.35rem',
                                borderRadius: '4px',
                                backgroundColor: 'rgba(245, 158, 11, 0.18)',
                                color: '#fbbf24',
                                border: '1px solid rgba(245, 158, 11, 0.35)',
                              }}
                            >
                              ⚡ DIV
                            </span>
                          )}
                        </div>
                        <span
                          className="terminal-badge"
                          style={{
                            backgroundColor:
                              item.pulse_index >= 15
                                ? 'rgba(16, 185, 129, 0.15)'
                                : item.pulse_index <= -15
                                ? 'rgba(244, 63, 94, 0.15)'
                                : 'rgba(148, 163, 184, 0.15)',
                            color:
                              item.pulse_index >= 15
                                ? '#34d399'
                                : item.pulse_index <= -15
                                ? '#fb7185'
                                : '#cbd5e1',
                          }}
                        >
                          {item.pulse_index >= 0 ? `+${item.pulse_index}` : item.pulse_index}
                        </span>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '130px' }}>
                          {item.topic.name}
                        </span>
                        <span style={{ fontFamily: 'var(--font-mono)' }}>
                          ${item.latest_price.toLocaleString()}{' '}
                          <span style={{ color: item.price_change_pct >= 0 ? '#34d399' : '#fb7185' }}>
                            ({item.price_change_pct >= 0 ? '+' : ''}
                            {item.price_change_pct}%)
                          </span>
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </aside>

            {/* MAIN MARKET LENS WORKSPACE */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* TOP METRIC CARDS */}
              <div className="card" style={{ padding: '1.35rem 1.5rem' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.35rem' }}>
                      <h1 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
                        {currentAsset.topic.name} ({currentAsset.topic.ticker})
                      </h1>
                      <span className="brand-badge">{currentAsset.top_drivers.sector}</span>
                      <button
                        onClick={() => handleToggleWatchlist(currentAsset.topic.slug)}
                        className="btn btn-outline"
                        style={{ padding: '0.25rem 0.65rem', fontSize: '0.78rem' }}
                      >
                        {watchlist.includes(currentAsset.topic.slug) ? '★ In Watchlist' : '☆ Add to Watchlist'}
                      </button>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', maxWidth: '720px' }}>
                      {currentAsset.synthesis}
                    </p>
                  </div>

                  <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Last EOD Price
                      </div>
                      <div style={{ fontSize: '1.65rem', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
                        ${currentAsset.latest_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                      <div
                        style={{
                          fontSize: '0.84rem',
                          fontWeight: 600,
                          fontFamily: 'var(--font-mono)',
                          color: currentAsset.price_change_pct >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)',
                        }}
                      >
                        {currentAsset.price_change >= 0 ? '+' : ''}
                        {currentAsset.price_change} ({currentAsset.price_change_pct >= 0 ? '+' : ''}
                        {currentAsset.price_change_pct}%)
                      </div>
                    </div>

                    <div
                      style={{
                        padding: '0.75rem 1.15rem',
                        borderRadius: '10px',
                        backgroundColor:
                          currentAsset.pulse_index >= 15
                            ? 'rgba(16, 185, 129, 0.14)'
                            : currentAsset.pulse_index <= -15
                            ? 'rgba(244, 63, 94, 0.14)'
                            : 'rgba(6, 182, 212, 0.14)',
                        border: '1px solid',
                        borderColor:
                          currentAsset.pulse_index >= 15
                            ? 'rgba(16, 185, 129, 0.4)'
                            : currentAsset.pulse_index <= -15
                            ? 'rgba(244, 63, 94, 0.4)'
                            : 'rgba(6, 182, 212, 0.4)',
                        textAlign: 'center',
                      }}
                    >
                      <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em', opacity: 0.85 }}>
                        Pulse Index
                      </div>
                      <div
                        style={{
                          fontSize: '1.75rem',
                          fontWeight: 800,
                          fontFamily: 'var(--font-mono)',
                          color:
                            currentAsset.pulse_index >= 15
                              ? '#34d399'
                              : currentAsset.pulse_index <= -15
                              ? '#fb7185'
                              : '#38bdf8',
                        }}
                      >
                        {currentAsset.pulse_index >= 0 ? `+${currentAsset.pulse_index}` : currentAsset.pulse_index}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                        FinBERT: {currentAsset.finbert_index >= 0 ? `+${currentAsset.finbert_index}` : currentAsset.finbert_index} (
                        {currentAsset.top_drivers.model_agreement_pct}% agree)
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* DUAL-AXIS SENTIMENT VS. PRICE INTERACTIVE CHART */}
              <div className="card" style={{ padding: '1.35rem 1.5rem' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
                  <div>
                    <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                      Sentiment vs. Price Movement & Divergence Overlay
                    </h2>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', gap: '1.15rem', marginTop: '0.25rem', flexWrap: 'wrap' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                        <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#06b6d4', display: 'inline-block' }} />
                        Price ($ USD)
                      </span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                        <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#10b981', display: 'inline-block' }} />
                        Pulse Sentiment Index (-100 to +100)
                      </span>
                      {showFinbertOverlay && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                          <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#a855f7', display: 'inline-block' }} />
                          FinBERT Domain Baseline
                        </span>
                      )}
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', color: '#fbbf24' }}>
                        ⚡ Divergence Alert Flag
                      </span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '0.45rem', alignItems: 'center' }}>
                    <button
                      onClick={() => setShowFinbertOverlay(!showFinbertOverlay)}
                      className="btn btn-outline"
                      style={{
                        padding: '0.3rem 0.65rem',
                        fontSize: '0.76rem',
                        borderColor: showFinbertOverlay ? '#a855f7' : 'var(--border-color)',
                        color: showFinbertOverlay ? '#c084fc' : 'var(--text-secondary)',
                      }}
                    >
                      {showFinbertOverlay ? '✓ FinBERT Overlay' : '+ FinBERT Overlay'}
                    </button>
                    {([7, 14, 30] as const).map((w) => (
                      <button
                        key={w}
                        onClick={() => setChartWindow(w)}
                        style={{
                          padding: '0.3rem 0.65rem',
                          borderRadius: '6px',
                          fontSize: '0.76rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          border: '1px solid',
                          borderColor: chartWindow === w ? 'var(--accent-cyan)' : 'var(--border-color)',
                          backgroundColor: chartWindow === w ? 'rgba(6, 182, 212, 0.18)' : 'transparent',
                          color: chartWindow === w ? '#38bdf8' : 'var(--text-secondary)',
                        }}
                      >
                        {w}D
                      </button>
                    ))}
                  </div>
                </div>

                {/* Live Hover Readout Bar */}
                {activeHoverPoint && (
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '1.25rem',
                      padding: '0.55rem 0.9rem',
                      borderRadius: '6px',
                      backgroundColor: 'rgba(15, 23, 42, 0.75)',
                      border: '1px solid var(--border-color)',
                      marginBottom: '0.75rem',
                      fontSize: '0.8rem',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    <span>
                      Date: <strong style={{ color: '#f8fafc' }}>{activeHoverPoint.date}</strong>
                    </span>
                    <span>
                      Close:{' '}
                      <strong style={{ color: '#38bdf8' }}>
                        ${activeHoverPoint.close_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </strong>{' '}
                      ({activeHoverPoint.change_pct >= 0 ? '+' : ''}
                      {activeHoverPoint.change_pct}%)
                    </span>
                    <span>
                      Pulse Index:{' '}
                      <strong style={{ color: activeHoverPoint.pulse_index >= 0 ? '#34d399' : '#fb7185' }}>
                        {activeHoverPoint.pulse_index >= 0 ? `+${activeHoverPoint.pulse_index}` : activeHoverPoint.pulse_index}
                      </strong>
                    </span>
                    <span>
                      FinBERT:{' '}
                      <strong style={{ color: '#c084fc' }}>
                        {activeHoverPoint.finbert_index >= 0 ? `+${activeHoverPoint.finbert_index}` : activeHoverPoint.finbert_index}
                      </strong>
                    </span>
                    <span>
                      Volume: <strong>{(activeHoverPoint.volume / 1_000_000).toFixed(1)}M</strong>
                    </span>
                    {activeHoverPoint.divergence_flag && (
                      <span style={{ color: '#fbbf24', fontWeight: 700 }}>
                        ⚡ {activeHoverPoint.divergence_type === 'bullish_divergence' ? 'BULLISH DIVERGENCE' : 'BEARISH DIVERGENCE'}
                      </span>
                    )}
                  </div>
                )}

                {/* SVG Dual-Axis Interactive Chart */}
                <div style={{ width: '100%', overflowX: 'auto' }}>
                  <svg
                    viewBox={`0 0 ${svgW} ${svgH}`}
                    style={{ width: '100%', height: 'auto', minWidth: '580px', display: 'block', userSelect: 'none' }}
                    onMouseLeave={() => setHoverIdx(null)}
                  >
                    <defs>
                      <linearGradient id="priceAreaGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.28" />
                        <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    {/* Horizontal Grid Lines & Zero Sentiment Baseline */}
                    {[0, 0.25, 0.5, 0.75, 1].map((ratio, idx) => {
                      const y = padT + ratio * plotH
                      const pVal = maxP - ratio * priceRange
                      const sVal = Math.round(100 - ratio * 200)
                      return (
                        <g key={idx}>
                          <line
                            x1={padL}
                            y1={y}
                            x2={svgW - padR}
                            y2={y}
                            stroke={sVal === 0 ? 'rgba(148, 163, 184, 0.35)' : 'rgba(35, 49, 73, 0.65)'}
                            strokeDasharray={sVal === 0 ? '4 4' : undefined}
                            strokeWidth={1}
                          />
                          <text x={padL - 8} y={y + 4} textAnchor="end" fill="#64748b" fontSize="10" fontFamily="monospace">
                            ${pVal >= 1000 ? pVal.toFixed(0) : pVal.toFixed(1)}
                          </text>
                          <text x={svgW - padR + 8} y={y + 4} textAnchor="start" fill="#64748b" fontSize="10" fontFamily="monospace">
                            {sVal > 0 ? `+${sVal}` : sVal}
                          </text>
                        </g>
                      )
                    })}

                    {/* Price Area & Line */}
                    <path d={priceAreaPath} fill="url(#priceAreaGrad)" />
                    <path d={pricePath} fill="none" stroke="#06b6d4" strokeWidth={2.5} />

                    {/* FinBERT Dotted Line */}
                    {showFinbertOverlay && (
                      <path d={finbertPath} fill="none" stroke="#a855f7" strokeWidth={1.6} strokeDasharray="4 4" />
                    )}

                    {/* Pulse Sentiment Index Line */}
                    <path d={sentPath} fill="none" stroke="#10b981" strokeWidth={2.4} />

                    {/* Data Points & Divergence Flags */}
                    {chartHistory.map((d, i) => {
                      const cx = xCoord(i)
                      const cyP = yPrice(d.close_price)
                      const cyS = ySent(d.pulse_index)
                      const isHovered = hoverIdx === i
                      return (
                        <g key={d.date}>
                          {isHovered && (
                            <line x1={cx} y1={padT} x2={cx} y2={padT + plotH} stroke="rgba(248, 250, 252, 0.35)" strokeDasharray="3 3" />
                          )}
                          <circle cx={cx} cy={cyP} r={isHovered ? 5 : 2.5} fill="#06b6d4" />
                          <circle
                            cx={cx}
                            cy={cyS}
                            r={d.divergence_flag ? 6 : isHovered ? 5 : 3}
                            fill={d.divergence_flag ? '#fbbf24' : d.pulse_index >= 0 ? '#10b981' : '#f43f5e'}
                            stroke="#0a0e17"
                            strokeWidth={1.5}
                          />
                          {d.divergence_flag && (
                            <text x={cx} y={cyS - 10} textAnchor="middle" fill="#fbbf24" fontSize="10" fontWeight="bold">
                              ⚡DIV
                            </text>
                          )}
                          {/* X-Axis Date Labels */}
                          {(i === 0 || i === chartHistory.length - 1 || i % Math.max(1, Math.floor(chartHistory.length / 6)) === 0) && (
                            <text x={cx} y={svgH - 10} textAnchor="middle" fill="#64748b" fontSize="10" fontFamily="monospace">
                              {d.date.slice(5)}
                            </text>
                          )}
                          {/* Invisible Hover Column */}
                          <rect
                            x={cx - plotW / chartHistory.length / 2}
                            y={padT}
                            width={plotW / chartHistory.length}
                            height={plotH}
                            fill="transparent"
                            style={{ cursor: 'crosshair' }}
                            onMouseEnter={() => setHoverIdx(i)}
                          />
                        </g>
                      )
                    })}
                  </svg>
                </div>
              </div>

              {/* 5-AGENT SOURCE CONSENSUS MATRIX */}
              <div className="card" style={{ padding: '1.25rem 1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>
                    Multi-Agent Source Consensus & Credibility Weighting
                  </h3>
                  <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    Formula: S = Σ(wᵢ · scoreᵢ) / Σwᵢ
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(155px, 1fr))', gap: '0.85rem' }}>
                  {Object.entries(AGENT_META).map(([key, meta]) => {
                    const score = currentAsset.top_drivers.agent_scores?.[key] ?? 0
                    const pct = Math.min(100, Math.max(5, Math.round((score + 100) / 2)))
                    return (
                      <div
                        key={key}
                        onClick={() => setSourceFilter(sourceFilter === key ? 'all' : key)}
                        style={{
                          padding: '0.85rem',
                          borderRadius: '8px',
                          backgroundColor: sourceFilter === key ? 'rgba(6, 182, 212, 0.14)' : 'rgba(15, 23, 42, 0.6)',
                          border: '1px solid',
                          borderColor: sourceFilter === key ? 'var(--accent-cyan)' : 'var(--border-color)',
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                          <span>{meta.badge}</span>
                          <span style={{ fontFamily: 'var(--font-mono)' }}>w={meta.weight}</span>
                        </div>
                        <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.45rem' }}>{meta.label}</div>
                        <div
                          style={{
                            fontSize: '1.25rem',
                            fontWeight: 800,
                            fontFamily: 'var(--font-mono)',
                            color: score >= 10 ? '#34d399' : score <= -10 ? '#fb7185' : '#38bdf8',
                            marginBottom: '0.4rem',
                          }}
                        >
                          {score >= 0 ? `+${score}` : score}
                        </div>
                        <div style={{ height: '5px', backgroundColor: '#1e293b', borderRadius: '999px', overflow: 'hidden' }}>
                          <div style={{ width: `${pct}%`, height: '100%', backgroundColor: meta.color }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* CATALYSTS VS. RISKS */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))', gap: '1.25rem' }}>
                <div className="card" style={{ borderLeft: '3px solid var(--accent-emerald)' }}>
                  <h3 style={{ fontSize: '0.98rem', fontWeight: 700, color: '#34d399', marginBottom: '0.75rem' }}>
                    🚀 Key Positive Catalysts & Bullish Drivers
                  </h3>
                  <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.86rem', color: '#e2e8f0' }}>
                    {currentAsset.top_drivers.positive_catalysts.map((c, idx) => (
                      <li key={idx} style={{ display: 'flex', gap: '0.5rem' }}>
                        <span style={{ color: '#34d399', fontWeight: 700 }}>+</span>
                        <span>{c}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="card" style={{ borderLeft: '3px solid var(--accent-rose)' }}>
                  <h3 style={{ fontSize: '0.98rem', fontWeight: 700, color: '#fb7185', marginBottom: '0.75rem' }}>
                    ⚠️ Key Downside Risks & Headwinds
                  </h3>
                  <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.86rem', color: '#e2e8f0' }}>
                    {currentAsset.top_drivers.risk_factors.map((r, idx) => (
                      <li key={idx} style={{ display: 'flex', gap: '0.5rem' }}>
                        <span style={{ color: '#fb7185', fontWeight: 700 }}>−</span>
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* SOURCE-CITED INTELLIGENCE FEED */}
              <div className="card" style={{ padding: '1.35rem 1.5rem' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
                  <div>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>
                      Verified Source-Cited Intelligence Feed ({filteredPosts.length} items)
                    </h3>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      Every synthesized signal links directly to its underlying news article or social thread.
                    </p>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                    <input
                      type="text"
                      placeholder="Filter headlines..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      style={{
                        padding: '0.38rem 0.75rem',
                        borderRadius: '6px',
                        border: '1px solid var(--border-color)',
                        backgroundColor: 'var(--bg-primary)',
                        color: 'var(--text-primary)',
                        fontSize: '0.8rem',
                      }}
                    />
                    <select
                      value={sourceFilter}
                      onChange={(e) => setSourceFilter(e.target.value)}
                      style={{
                        padding: '0.38rem 0.65rem',
                        borderRadius: '6px',
                        border: '1px solid var(--border-color)',
                        backgroundColor: 'var(--bg-primary)',
                        color: 'var(--text-primary)',
                        fontSize: '0.8rem',
                      }}
                    >
                      <option value="all">All Sources (5 Agents)</option>
                      <option value="yahoo">Yahoo Finance</option>
                      <option value="gdelt">GDELT Global News</option>
                      <option value="reddit">Reddit Subreddits</option>
                      <option value="stocktwits">StockTwits</option>
                      <option value="bluesky">Bluesky</option>
                    </select>
                    <select
                      value={sentimentFilter}
                      onChange={(e) => setSentimentFilter(e.target.value)}
                      style={{
                        padding: '0.38rem 0.65rem',
                        borderRadius: '6px',
                        border: '1px solid var(--border-color)',
                        backgroundColor: 'var(--bg-primary)',
                        color: 'var(--text-primary)',
                        fontSize: '0.8rem',
                      }}
                    >
                      <option value="all">All Sentiments</option>
                      <option value="positive">Positive Only</option>
                      <option value="neutral">Neutral Only</option>
                      <option value="negative">Negative Only</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {filteredPosts.map((post) => {
                    const isPos = post.sentiment_label === 'positive'
                    const isNeg = post.sentiment_label === 'negative'
                    return (
                      <div
                        key={post.external_id}
                        style={{
                          padding: '0.95rem 1.1rem',
                          borderRadius: '8px',
                          backgroundColor: 'rgba(15, 23, 42, 0.55)',
                          border: '1px solid var(--border-color)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.45rem',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                          <a
                            href={post.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ fontWeight: 600, fontSize: '0.93rem', color: '#f8fafc', textDecoration: 'underline', textDecorationColor: 'rgba(6,182,212,0.4)' }}
                          >
                            {post.title} ↗
                          </a>
                          <div style={{ display: 'flex', gap: '0.4rem', flexShrink: 0 }}>
                            <span
                              className="terminal-badge"
                              style={{
                                backgroundColor: isPos
                                  ? 'rgba(16, 185, 129, 0.16)'
                                  : isNeg
                                  ? 'rgba(244, 63, 94, 0.16)'
                                  : 'rgba(148, 163, 184, 0.16)',
                                color: isPos ? '#34d399' : isNeg ? '#fb7185' : '#cbd5e1',
                              }}
                            >
                              {post.sentiment_label.toUpperCase()} {post.sentiment_score >= 0 ? `+${post.sentiment_score}` : post.sentiment_score}
                            </span>
                            <span
                              className="terminal-badge"
                              style={{
                                backgroundColor: 'rgba(168, 85, 247, 0.14)',
                                color: '#c084fc',
                                border: '1px solid rgba(168, 85, 247, 0.3)',
                              }}
                            >
                              FinBERT: {post.finbert_score >= 0 ? `+${post.finbert_score}` : post.finbert_score}
                            </span>
                          </div>
                        </div>

                        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                          <div style={{ display: 'flex', gap: '0.85rem', alignItems: 'center' }}>
                            <span style={{ color: 'var(--accent-cyan)', fontWeight: 600, textTransform: 'uppercase' }}>
                              {post.source} • {post.outlet}
                            </span>
                            <span>Engagement: {post.engagement_count.toLocaleString()}</span>
                            <span>Confidence: {(post.confidence * 100).toFixed(0)}%</span>
                          </div>
                          <div style={{ display: 'flex', gap: '0.35rem' }}>
                            {post.theme_tags.slice(0, 3).map((tag) => (
                              <span
                                key={tag}
                                style={{
                                  padding: '0.1rem 0.4rem',
                                  borderRadius: '4px',
                                  backgroundColor: 'rgba(30, 41, 59, 0.9)',
                                  color: '#94a3b8',
                                  fontFamily: 'var(--font-mono)',
                                  fontSize: '0.68rem',
                                }}
                              >
                                #{tag}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ===================================================================
            TAB 2: BRAND LENS (COMPETITOR SHARE OF VOICE & PRAISE/COMPLAINT)
           =================================================================== */}
        {activeTab === 'brand' && primaryBrand && competitorBrand && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="card" style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
              <div>
                <h1 style={{ fontSize: '1.55rem', fontWeight: 800 }}>
                  🏷️ Brand Lens — Competitor Share-of-Voice & Reputation Intelligence
                </h1>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
                  Compare consumer praise, product grievances, and media volume across industry rivals.
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <div>
                  <label style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>Primary Brand / Asset</label>
                  <select
                    value={brandPrimarySlug}
                    onChange={(e) => setBrandPrimarySlug(e.target.value)}
                    style={{
                      padding: '0.45rem 0.85rem',
                      borderRadius: '6px',
                      backgroundColor: 'var(--bg-primary)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--accent-cyan)',
                      fontWeight: 600,
                    }}
                  >
                    {assets.map((a) => (
                      <option key={a.topic.slug} value={a.topic.slug}>
                        {a.topic.name} ({a.topic.ticker})
                      </option>
                    ))}
                  </select>
                </div>

                <span style={{ fontWeight: 800, color: 'var(--text-muted)', marginTop: '1rem' }}>VS.</span>

                <div>
                  <label style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>Competitor Benchmark</label>
                  <select
                    value={compareSlug}
                    onChange={(e) => setCompareSlug(e.target.value)}
                    style={{
                      padding: '0.45rem 0.85rem',
                      borderRadius: '6px',
                      backgroundColor: 'var(--bg-primary)',
                      color: 'var(--text-primary)',
                      border: '1px solid #a855f7',
                      fontWeight: 600,
                    }}
                  >
                    {assets.map((a) => (
                      <option key={a.topic.slug} value={a.topic.slug}>
                        {a.topic.name} ({a.topic.ticker})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* HEAD-TO-HEAD CARDS */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1.25rem' }}>
              {[
                { item: primaryBrand, accent: '#06b6d4', tag: 'PRIMARY BRAND' },
                { item: competitorBrand, accent: '#a855f7', tag: 'COMPETITOR' },
              ].map(({ item, accent, tag }) => {
                const total = Math.max(1, item.positive_count + item.neutral_count + item.negative_count)
                const praisePct = Math.round((item.positive_count / total) * 100)
                const complaintPct = Math.round((item.negative_count / total) * 100)
                return (
                  <div key={item.topic.slug} className="card" style={{ borderTop: `3px solid ${accent}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                      <div>
                        <span style={{ fontSize: '0.7rem', color: accent, fontWeight: 700 }}>{tag}</span>
                        <h2 style={{ fontSize: '1.4rem', fontWeight: 800 }}>
                          {item.topic.name} ({item.topic.ticker})
                        </h2>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Brand Pulse Index</div>
                        <div
                          style={{
                            fontSize: '1.65rem',
                            fontWeight: 800,
                            fontFamily: 'var(--font-mono)',
                            color: item.pulse_index >= 0 ? '#34d399' : '#fb7185',
                          }}
                        >
                          {item.pulse_index >= 0 ? `+${item.pulse_index}` : item.pulse_index}
                        </div>
                      </div>
                    </div>

                    {/* Praise vs. Complaint Bar */}
                    <div style={{ marginBottom: '1.15rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '0.35rem' }}>
                        <span style={{ color: '#34d399', fontWeight: 600 }}>👍 Praise ({praisePct}%)</span>
                        <span style={{ color: '#94a3b8' }}>Neutral ({100 - praisePct - complaintPct}%)</span>
                        <span style={{ color: '#fb7185', fontWeight: 600 }}>👎 Complaints ({complaintPct}%)</span>
                      </div>
                      <div style={{ display: 'flex', height: '10px', borderRadius: '999px', overflow: 'hidden', backgroundColor: '#1e293b' }}>
                        <div style={{ width: `${praisePct}%`, backgroundColor: '#10b981' }} />
                        <div style={{ width: `${100 - praisePct - complaintPct}%`, backgroundColor: '#475569' }} />
                        <div style={{ width: `${complaintPct}%`, backgroundColor: '#f43f5e' }} />
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                      <div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#34d399', marginBottom: '0.25rem' }}>
                          Top Brand Praise Catalysts:
                        </div>
                        {item.top_drivers.positive_catalysts.slice(0, 2).map((c, i) => (
                          <div key={i} style={{ fontSize: '0.82rem', color: '#cbd5e1', marginBottom: '0.2rem' }}>
                            • {c}
                          </div>
                        ))}
                      </div>
                      <div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#fb7185', marginBottom: '0.25rem' }}>
                          Top Customer / Market Complaints:
                        </div>
                        {item.top_drivers.risk_factors.slice(0, 2).map((r, i) => (
                          <div key={i} style={{ fontSize: '0.82rem', color: '#cbd5e1', marginBottom: '0.2rem' }}>
                            • {r}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* ===================================================================
            TAB 3: BACKTESTING & ALPHA CORRELATION LAB
           =================================================================== */}
        {activeTab === 'backtest' && backtestStats && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="card">
              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
                <div>
                  <h1 style={{ fontSize: '1.5rem', fontWeight: 800 }}>
                    🧪 Sentiment-to-Price Backtesting Lab — {currentAsset.topic.name} ({currentAsset.topic.ticker})
                  </h1>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
                    Evaluates how accurately Pulse Sentiment Index signals predicted forward asset price direction.
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block' }}>
                      Signal Conviction Threshold: <strong>|Pulse| ≥ {btThreshold}</strong>
                    </label>
                    <input
                      type="range"
                      min={5}
                      max={45}
                      step={1}
                      value={btThreshold}
                      onChange={(e) => setBtThreshold(Number(e.target.value))}
                      style={{ width: '180px', accentColor: 'var(--accent-cyan)' }}
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.25rem' }}>
                      Forward Holding Horizon
                    </label>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      {([1, 3] as const).map((h) => (
                        <button
                          key={h}
                          onClick={() => setBtHorizon(h)}
                          className="btn btn-outline"
                          style={{
                            padding: '0.3rem 0.7rem',
                            fontSize: '0.78rem',
                            borderColor: btHorizon === h ? 'var(--accent-cyan)' : 'var(--border-color)',
                            color: btHorizon === h ? '#38bdf8' : 'var(--text-secondary)',
                          }}
                        >
                          T+{h} Day{h > 1 ? 's' : ''}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* BACKTEST KPI CARDS */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '1rem' }}>
              <div className="card">
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Directional Hit Rate
                </div>
                <div style={{ fontSize: '2rem', fontWeight: 800, color: '#34d399', fontFamily: 'var(--font-mono)' }}>
                  {backtestStats.hitRate}%
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  {backtestStats.wins} wins of {backtestStats.totalTrades} triggered signals
                </div>
              </div>

              <div className="card">
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Pulse Strategy Return
                </div>
                <div
                  style={{
                    fontSize: '2rem',
                    fontWeight: 800,
                    color: backtestStats.stratTotalRet >= 0 ? '#38bdf8' : '#fb7185',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {backtestStats.stratTotalRet >= 0 ? '+' : ''}
                  {backtestStats.stratTotalRet}%
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  vs. Buy & Hold ({backtestStats.bhTotalRet >= 0 ? '+' : ''}
                  {backtestStats.bhTotalRet}%)
                </div>
              </div>

              <div className="card">
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Net Sentiment Alpha
                </div>
                <div
                  style={{
                    fontSize: '2rem',
                    fontWeight: 800,
                    color: backtestStats.alpha >= 0 ? '#34d399' : '#fbbf24',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {backtestStats.alpha >= 0 ? '+' : ''}
                  {backtestStats.alpha}%
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  Excess return over benchmark
                </div>
              </div>

              <div className="card">
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Divergence Signal Win Rate
                </div>
                <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fbbf24', fontFamily: 'var(--font-mono)' }}>
                  {backtestStats.divHitRate}%
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  High-conviction divergence flags
                </div>
              </div>
            </div>

            {/* TRADE LOG TABLE */}
            <div className="card">
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '1rem' }}>
                Historical Signal Execution Ledger ({backtestStats.trades.length} signals)
              </h3>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '0.65rem' }}>Signal Date</th>
                      <th style={{ padding: '0.65rem' }}>Pulse Index</th>
                      <th style={{ padding: '0.65rem' }}>Position Signal</th>
                      <th style={{ padding: '0.65rem' }}>Entry Price</th>
                      <th style={{ padding: '0.65rem' }}>T+{btHorizon} Exit Price</th>
                      <th style={{ padding: '0.65rem' }}>Asset Return</th>
                      <th style={{ padding: '0.65rem' }}>Outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {backtestStats.trades.map((tr, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(35, 49, 73, 0.5)' }}>
                        <td style={{ padding: '0.65rem', fontFamily: 'var(--font-mono)' }}>{tr.date}</td>
                        <td
                          style={{
                            padding: '0.65rem',
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 700,
                            color: tr.pulse_index >= 0 ? '#34d399' : '#fb7185',
                          }}
                        >
                          {tr.pulse_index >= 0 ? `+${tr.pulse_index}` : tr.pulse_index}
                        </td>
                        <td style={{ padding: '0.65rem' }}>
                          <span
                            className="terminal-badge"
                            style={{
                              backgroundColor: tr.direction === 'LONG' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
                              color: tr.direction === 'LONG' ? '#34d399' : '#fb7185',
                            }}
                          >
                            {tr.direction}
                          </span>
                          {tr.is_divergence && (
                            <span style={{ marginLeft: '0.4rem', color: '#fbbf24', fontSize: '0.75rem' }}>⚡ DIV</span>
                          )}
                        </td>
                        <td style={{ padding: '0.65rem', fontFamily: 'var(--font-mono)' }}>${tr.entry_price.toFixed(2)}</td>
                        <td style={{ padding: '0.65rem', fontFamily: 'var(--font-mono)' }}>${tr.exit_price.toFixed(2)}</td>
                        <td
                          style={{
                            padding: '0.65rem',
                            fontFamily: 'var(--font-mono)',
                            color: tr.forward_return_pct >= 0 ? '#34d399' : '#fb7185',
                          }}
                        >
                          {tr.forward_return_pct >= 0 ? '+' : ''}
                          {tr.forward_return_pct}%
                        </td>
                        <td style={{ padding: '0.65rem' }}>
                          <span
                            className="terminal-badge"
                            style={{
                              backgroundColor: tr.correct ? 'rgba(16, 185, 129, 0.2)' : 'rgba(244, 63, 94, 0.2)',
                              color: tr.correct ? '#34d399' : '#fb7185',
                            }}
                          >
                            {tr.correct ? '✓ ACCURATE' : '✗ MISS'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ===================================================================
            TAB 4: SOCIAL RADAR (USER & INFLUENCER MONITORING AGENTS)
           =================================================================== */}
        {activeTab === 'social' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="card">
              <h1 style={{ fontSize: '1.5rem', fontWeight: 800, marginBottom: '0.3rem' }}>
                📡 Social Radar — Executive Account & Analyst Stream Monitoring
              </h1>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
                Powered by <code>RedditUserAgent</code>, <code>StockTwitsUserAgent</code>, and <code>BlueskyUserAgent</code> with automated post deduplication.
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1.25rem' }}>
              {socialRadar.map((sr) => (
                <div key={sr.handle} className="card" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <span className="brand-badge">{sr.platform} Agent</span>
                      <h2 style={{ fontSize: '1.3rem', fontWeight: 800, marginTop: '0.35rem' }}>{sr.handle}</h2>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{sr.role}</div>
                    </div>
                    <span className="terminal-badge badge-bullish">{sr.sentiment_signal}</span>
                  </div>

                  <p style={{ fontSize: '0.86rem', color: '#cbd5e1', lineHeight: 1.55 }}>{sr.executive_summary}</p>

                  <div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase', marginBottom: '0.4rem' }}>
                      Recent Milestones & Submissions
                    </div>
                    <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.45rem', fontSize: '0.82rem', color: '#e2e8f0' }}>
                      {sr.milestones.map((m, idx) => (
                        <li
                          key={idx}
                          style={{
                            padding: '0.5rem 0.65rem',
                            borderRadius: '6px',
                            backgroundColor: 'rgba(15, 23, 42, 0.65)',
                            border: '1px solid var(--border-color)',
                          }}
                        >
                          {m}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===================================================================
            TAB 5: SCHEDULED INGESTION & PIPELINE CONTROL CENTER
           =================================================================== */}
        {activeTab === 'pipeline' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="card" style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
              <div>
                <h1 style={{ fontSize: '1.5rem', fontWeight: 800, marginBottom: '0.3rem' }}>
                  ⚙️ Scheduled Ingestion & Multi-Agent Pipeline Control Center
                </h1>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
                  Automated 6-hour <code>pg_cron</code> rollups inside Supabase PostgreSQL paired with the Python Multi-Agent Orchestrator.
                </p>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button
                  onClick={() => handleTriggerIngestion()}
                  disabled={isIngesting}
                  className="btn btn-primary"
                  style={{ padding: '0.65rem 1.25rem' }}
                >
                  {isIngesting ? '⏳ Running All 8 Agents...' : '🚀 Run Full Scheduled Ingestion Now (All 14 Topics)'}
                </button>
              </div>
            </div>

            {/* PIPELINE ARCHITECTURE STATUS */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
              <div className="card">
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Supabase pg_cron Schedule
                </div>
                <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#34d399', fontFamily: 'var(--font-mono)', marginTop: '0.25rem' }}>
                  0 */6 * * * (ACTIVE)
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                  Job: <code>pulse-6h-signal-rollup</code>
                </div>
              </div>

              <div className="card">
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Connected Intelligence Agents
                </div>
                <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'var(--font-mono)', marginTop: '0.25rem' }}>
                  8 Agents Operational
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                  Yahoo, GDELT, Reddit, StockTwits, Bluesky
                </div>
              </div>

              <div className="card">
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Supabase Database Volume
                </div>
                <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#c084fc', fontFamily: 'var(--font-mono)', marginTop: '0.25rem' }}>
                  14 Topics • 420 Bars
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                  297 Source-Cited Posts & RLS Active
                </div>
              </div>
            </div>

            {/* INGESTION RUNS AUDIT TABLE */}
            <div className="card">
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '1rem' }}>
                Live Supabase Scheduled Ingestion Audit Log (<code>public.scheduled_ingestion_runs</code>)
              </h3>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '0.65rem' }}>Timestamp</th>
                      <th style={{ padding: '0.65rem' }}>Trigger Source</th>
                      <th style={{ padding: '0.65rem' }}>Status</th>
                      <th style={{ padding: '0.65rem' }}>Topics</th>
                      <th style={{ padding: '0.65rem' }}>Posts Scored</th>
                      <th style={{ padding: '0.65rem' }}>Daily Bars</th>
                      <th style={{ padding: '0.65rem' }}>Duration</th>
                      <th style={{ padding: '0.65rem' }}>Summary Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr key={run.id} style={{ borderBottom: '1px solid rgba(35, 49, 73, 0.5)' }}>
                        <td style={{ padding: '0.65rem', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>
                          {new Date(run.completed_at).toLocaleString()}
                        </td>
                        <td style={{ padding: '0.65rem' }}>
                          <span className="brand-badge">{run.trigger_source}</span>
                        </td>
                        <td style={{ padding: '0.65rem' }}>
                          <span className="terminal-badge badge-bullish">{run.status.toUpperCase()}</span>
                        </td>
                        <td style={{ padding: '0.65rem', fontFamily: 'var(--font-mono)' }}>{run.topics_processed}</td>
                        <td style={{ padding: '0.65rem', fontFamily: 'var(--font-mono)' }}>{run.posts_ingested}</td>
                        <td style={{ padding: '0.65rem', fontFamily: 'var(--font-mono)' }}>{run.signals_updated}</td>
                        <td style={{ padding: '0.65rem', fontFamily: 'var(--font-mono)' }}>{run.duration_ms} ms</td>
                        <td style={{ padding: '0.65rem', color: 'var(--text-secondary)' }}>{run.summary_notes}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

