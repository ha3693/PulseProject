'use client'

import React, { useState, useMemo, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AssetSignal, IngestionRunLog } from './PulseTerminal'

interface WatchlistEntry {
  slug: string
  notes: string
}

interface PersonalDashboardProps {
  userEmail: string
  userId: string
  fullName?: string | null
  assets: AssetSignal[]
  initialWatchlist: WatchlistEntry[]
  recentRuns: IngestionRunLog[]
}

export default function PersonalDashboard({
  userEmail,
  userId,
  fullName,
  assets,
  initialWatchlist,
  recentRuns,
}: PersonalDashboardProps) {
  const router = useRouter()
  const [watchedEntries, setWatchedEntries] = useState<WatchlistEntry[]>(
    initialWatchlist.length > 0
      ? initialWatchlist
      : [
          { slug: 'nvda', notes: 'Core AI infrastructure holding — monitoring Blackwell ramp & options flow' },
          { slug: 'aapl', notes: 'Watching consumer upgrade cycle sentiment vs. services growth' },
          { slug: 'btc-usd', notes: 'Macro liquidity proxy & institutional ETF inflow tracker' },
          { slug: 'nike', notes: 'Brand turnaround tracking vs. Adidas share-of-voice' },
        ]
  )
  const [editingNoteSlug, setEditingNoteSlug] = useState<string | null>(null)
  const [noteDraft, setNoteDraft] = useState<string>('')
  const [statusToast, setStatusToast] = useState<string | null>(null)
  const [selectedAddSlug, setSelectedAddSlug] = useState<string>('msft')

  useEffect(() => {
    if (initialWatchlist && initialWatchlist.length > 0) {
      setWatchedEntries(initialWatchlist)
    }
  }, [initialWatchlist])

  useEffect(() => {
    let active = true
    async function syncWatchlist() {
      try {
        const res = await fetch('/api/watchlist', { cache: 'no-store' })
        if (!res.ok) return
        const data = await res.json()
        if (active && data?.authenticated && Array.isArray(data.items)) {
          const mapped = data.items
            .map((item: any) => ({
              slug: item.topic?.slug,
              notes: item.notes || 'Monitoring daily sentiment vs. price action',
            }))
            .filter((item: any) => Boolean(item.slug))
          setWatchedEntries(mapped)
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

  const watchedSlugs = useMemo(() => watchedEntries.map((w) => w.slug), [watchedEntries])

  const watchedAssets = useMemo(
    () => assets.filter((a) => watchedSlugs.includes(a.topic.slug)),
    [assets, watchedSlugs]
  )

  const unwatchedAssets = useMemo(
    () => assets.filter((a) => !watchedSlugs.includes(a.topic.slug)),
    [assets, watchedSlugs]
  )

  useEffect(() => {
    if (unwatchedAssets.length > 0 && (!selectedAddSlug || watchedSlugs.includes(selectedAddSlug))) {
      setSelectedAddSlug(unwatchedAssets[0].topic.slug)
    }
  }, [unwatchedAssets, watchedSlugs, selectedAddSlug])

  // Portfolio-level aggregated metrics
  const portfolioStats = useMemo(() => {
    if (watchedAssets.length === 0) {
      return { avgPulse: 0, avgFinbert: 0, bullCount: 0, bearCount: 0, divCount: 0, avgChangePct: 0 }
    }
    const sumPulse = watchedAssets.reduce((acc, a) => acc + a.pulse_index, 0)
    const sumFb = watchedAssets.reduce((acc, a) => acc + a.finbert_index, 0)
    const sumChg = watchedAssets.reduce((acc, a) => acc + a.price_change_pct, 0)
    const bullCount = watchedAssets.filter((a) => a.pulse_index >= 15).length
    const bearCount = watchedAssets.filter((a) => a.pulse_index <= -15).length
    const divCount = watchedAssets.filter(
      (a) => a.divergence_flag || a.history.slice(-5).some((h) => h.divergence_flag)
    ).length

    return {
      avgPulse: Number((sumPulse / watchedAssets.length).toFixed(1)),
      avgFinbert: Number((sumFb / watchedAssets.length).toFixed(1)),
      avgChangePct: Number((sumChg / watchedAssets.length).toFixed(2)),
      bullCount,
      bearCount,
      divCount,
    }
  }, [watchedAssets])

  // Curated intelligence feed exclusively for watched assets
  const portfolioFeed = useMemo(() => {
    const items: Array<{ ticker: string; slug: string; post: AssetSignal['posts'][0] }> = []
    watchedAssets.forEach((asset) => {
      asset.posts.slice(0, 4).forEach((p) => {
        items.push({ ticker: asset.topic.ticker, slug: asset.topic.slug, post: p })
      })
    })
    return items.slice(0, 12)
  }, [watchedAssets])

  async function handleAddAsset(slugToAdd: string) {
    if (!slugToAdd || watchedSlugs.includes(slugToAdd)) return
    const defaultNote = 'Tracking daily sentiment & divergence signals'
    const next = [...watchedEntries, { slug: slugToAdd, notes: defaultNote }]
    setWatchedEntries(next)
    setStatusToast(`Added ${slugToAdd.toUpperCase()} to your Supabase Watchlist`)
    setTimeout(() => setStatusToast(null), 3500)

    try {
      await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug: slugToAdd, notes: defaultNote }),
      })
      window.dispatchEvent(new CustomEvent('pulse-watchlist-updated'))
      router.refresh()
    } catch {
      // Optimistic UI updated
    }
  }

  async function handleRemoveAsset(slugToRemove: string) {
    setWatchedEntries(watchedEntries.filter((w) => w.slug !== slugToRemove))
    setStatusToast(`Removed ${slugToRemove.toUpperCase()} from your Watchlist`)
    setTimeout(() => setStatusToast(null), 3500)

    try {
      await fetch(`/api/watchlist?slug=${encodeURIComponent(slugToRemove)}`, { method: 'DELETE' })
      window.dispatchEvent(new CustomEvent('pulse-watchlist-updated'))
      router.refresh()
    } catch {
      // Optimistic UI updated
    }
  }

  async function handleSaveNote(slug: string) {
    setWatchedEntries(
      watchedEntries.map((w) => (w.slug === slug ? { ...w, notes: noteDraft } : w))
    )
    setEditingNoteSlug(null)
    setStatusToast(`Saved research note for ${slug.toUpperCase()} to Supabase`)
    setTimeout(() => setStatusToast(null), 3500)

    try {
      await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug, notes: noteDraft }),
      })
      window.dispatchEvent(new CustomEvent('pulse-watchlist-updated'))
      router.refresh()
    } catch {
      // Optimistic UI updated
    }
  }

  return (
    <div className="container" style={{ paddingTop: '2rem', paddingBottom: '4rem' }}>
      {statusToast && (
        <div
          style={{
            padding: '0.75rem 1.25rem',
            borderRadius: '8px',
            background: 'linear-gradient(90deg, rgba(16,185,129,0.2), rgba(6,182,212,0.16))',
            border: '1px solid rgba(16,185,129,0.45)',
            color: '#f8fafc',
            marginBottom: '1.25rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.88rem',
          }}
        >
          <span>✅ {statusToast}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#34d399' }}>
            public.user_watchlists (RLS Active)
          </span>
        </div>
      )}

      {/* 1. PERSONAL COMMAND HEADER */}
      <div
        className="card"
        style={{
          padding: '1.6rem 1.8rem',
          marginBottom: '1.5rem',
          background: 'linear-gradient(135deg, rgba(16, 24, 41, 0.95), rgba(12, 18, 32, 0.92))',
          border: '1px solid rgba(6, 182, 212, 0.35)',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1.25rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
              <span className="live-dot-pill">
                <span className="pulse-dot" /> AUTHENTICATED PORTFOLIO COMMAND
              </span>
              <span className="brand-badge">Supabase RLS Protected</span>
            </div>
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
              Welcome back, {fullName || userEmail.split('@')[0]}
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
              Personal Sentiment & Divergence Command Center • Account: <span style={{ color: '#38bdf8' }}>{userEmail}</span>
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <Link href="/terminal" className="btn btn-primary" style={{ padding: '0.6rem 1.2rem' }}>
              ⚡ Launch Deep-Dive Terminal →
            </Link>
            <Link href="/account" className="btn btn-outline" style={{ padding: '0.6rem 1rem' }}>
              ⚙️ Profile Settings
            </Link>
          </div>
        </div>
      </div>

      {/* 2. PORTFOLIO-LEVEL KPI SUMMARY CARDS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.75rem' }}>
        <div className="card">
          <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Portfolio Pulse Index
          </div>
          <div
            style={{
              fontSize: '2rem',
              fontWeight: 800,
              fontFamily: 'var(--font-mono)',
              color: portfolioStats.avgPulse >= 0 ? '#34d399' : '#fb7185',
              marginTop: '0.2rem',
            }}
          >
            {portfolioStats.avgPulse >= 0 ? `+${portfolioStats.avgPulse}` : portfolioStats.avgPulse}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            FinBERT Avg: {portfolioStats.avgFinbert >= 0 ? `+${portfolioStats.avgFinbert}` : portfolioStats.avgFinbert}
          </div>
        </div>

        <div className="card">
          <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Watched Assets Breakdown
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#f8fafc', marginTop: '0.2rem' }}>
            {watchedAssets.length} <span style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>/ {assets.length}</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            <span style={{ color: '#34d399' }}>{portfolioStats.bullCount} Bullish</span> •{' '}
            <span style={{ color: '#fb7185' }}>{portfolioStats.bearCount} Bearish</span>
          </div>
        </div>

        <div className="card">
          <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Portfolio Daily Avg Move
          </div>
          <div
            style={{
              fontSize: '2rem',
              fontWeight: 800,
              fontFamily: 'var(--font-mono)',
              color: portfolioStats.avgChangePct >= 0 ? '#38bdf8' : '#fb7185',
              marginTop: '0.2rem',
            }}
          >
            {portfolioStats.avgChangePct >= 0 ? '+' : ''}
            {portfolioStats.avgChangePct}%
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            Equal-weighted daily change
          </div>
        </div>

        <div className="card">
          <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Active Divergence Alerts
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#fbbf24', marginTop: '0.2rem' }}>
            {portfolioStats.divCount} ⚡
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            Price vs. sentiment dislocation
          </div>
        </div>
      </div>

      {/* 3. MY WATCHED ASSETS & ANALYST NOTES */}
      <div className="card" style={{ marginBottom: '1.75rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '1.25rem' }}>
          <div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 800 }}>
              ★ My Watched Portfolio & Personal Analyst Notes
            </h2>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
              Customize your tracked tickers and save personal diligence notes directly to Supabase.
            </p>
          </div>

          {unwatchedAssets.length > 0 && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <select
                value={selectedAddSlug}
                onChange={(e) => setSelectedAddSlug(e.target.value)}
                style={{
                  padding: '0.45rem 0.75rem',
                  borderRadius: '6px',
                  backgroundColor: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  fontSize: '0.84rem',
                }}
              >
                {unwatchedAssets.map((a) => (
                  <option key={a.topic.slug} value={a.topic.slug}>
                    + {a.topic.ticker} — {a.topic.name}
                  </option>
                ))}
              </select>
              <button
                onClick={() => handleAddAsset(selectedAddSlug || unwatchedAssets[0]?.topic.slug)}
                className="btn btn-primary"
                style={{ padding: '0.45rem 0.9rem', fontSize: '0.82rem' }}
              >
                + Add to Portfolio
              </button>
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.15rem' }}>
          {watchedAssets.map((item) => {
            const entry = watchedEntries.find((w) => w.slug === item.topic.slug)
            const recentBars = item.history.slice(-14)
            const minP = Math.min(...recentBars.map((b) => b.close_price))
            const maxP = Math.max(...recentBars.map((b) => b.close_price))
            const pRange = Math.max(maxP - minP, 0.01)
            const sparkPoints = recentBars
              .map((b, i) => {
                const x = (i / Math.max(1, recentBars.length - 1)) * 120
                const y = 34 - ((b.close_price - minP) / pRange) * 28
                return `${x.toFixed(1)},${y.toFixed(1)}`
              })
              .join(' ')

            const hasDiv = item.divergence_flag || item.history.slice(-5).some((h) => h.divergence_flag)

            return (
              <div
                key={item.topic.slug}
                style={{
                  padding: '1.15rem',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(12, 18, 32, 0.85)',
                  border: '1px solid var(--border-color)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.85rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                      <span style={{ fontSize: '1.2rem', fontWeight: 800 }}>{item.topic.ticker}</span>
                      <span className="brand-badge">{item.top_drivers.sector}</span>
                      {hasDiv && (
                        <span
                          style={{
                            fontSize: '0.68rem',
                            padding: '0.1rem 0.4rem',
                            borderRadius: '4px',
                            backgroundColor: 'rgba(245, 158, 11, 0.18)',
                            color: '#fbbf24',
                            fontWeight: 700,
                          }}
                        >
                          ⚡ DIVERGENCE
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{item.topic.name}</div>
                  </div>

                  {/* 14-Day Mini Sparkline */}
                  <svg width="124" height="38" style={{ overflow: 'visible' }}>
                    <polyline
                      fill="none"
                      stroke={item.price_change_pct >= 0 ? '#10b981' : '#f43f5e'}
                      strokeWidth="2"
                      points={sparkPoints}
                    />
                  </svg>
                </div>

                {/* Metrics Row */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: '0.5rem',
                    padding: '0.6rem 0.75rem',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(6, 9, 17, 0.65)',
                    border: '1px solid rgba(45, 62, 94, 0.45)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>PRICE</div>
                    <div style={{ fontSize: '0.92rem', fontWeight: 700 }}>
                      ${item.latest_price.toLocaleString()}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: item.price_change_pct >= 0 ? '#34d399' : '#fb7185' }}>
                      {item.price_change_pct >= 0 ? '+' : ''}
                      {item.price_change_pct}%
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>PULSE INDEX</div>
                    <div
                      style={{
                        fontSize: '1.05rem',
                        fontWeight: 800,
                        color: item.pulse_index >= 0 ? '#34d399' : '#fb7185',
                      }}
                    >
                      {item.pulse_index >= 0 ? `+${item.pulse_index}` : item.pulse_index}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>FINBERT</div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#c084fc' }}>
                      {item.finbert_index >= 0 ? `+${item.finbert_index}` : item.finbert_index}
                    </div>
                  </div>
                </div>

                {/* Personal Analyst Note */}
                <div
                  style={{
                    padding: '0.65rem 0.8rem',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(15, 23, 42, 0.5)',
                    borderLeft: '2px solid var(--accent-cyan)',
                    fontSize: '0.8rem',
                  }}
                >
                  {editingNoteSlug === item.topic.slug ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                      <input
                        type="text"
                        value={noteDraft}
                        onChange={(e) => setNoteDraft(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '0.4rem 0.6rem',
                          borderRadius: '4px',
                          border: '1px solid var(--accent-cyan)',
                          backgroundColor: 'var(--bg-primary)',
                          color: 'var(--text-primary)',
                          fontSize: '0.8rem',
                        }}
                      />
                      <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <button
                          onClick={() => handleSaveNote(item.topic.slug)}
                          className="btn btn-primary"
                          style={{ padding: '0.25rem 0.65rem', fontSize: '0.74rem' }}
                        >
                          Save Note
                        </button>
                        <button
                          onClick={() => setEditingNoteSlug(null)}
                          className="btn btn-outline"
                          style={{ padding: '0.25rem 0.65rem', fontSize: '0.74rem' }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ color: '#cbd5e1' }}>
                        📝 <strong>My Thesis:</strong> {entry?.notes || 'Click Edit to add personal research notes.'}
                      </span>
                      <button
                        onClick={() => {
                          setEditingNoteSlug(item.topic.slug)
                          setNoteDraft(entry?.notes || '')
                        }}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--accent-cyan)',
                          cursor: 'pointer',
                          fontSize: '0.75rem',
                          flexShrink: 0,
                        }}
                      >
                        Edit
                      </button>
                    </div>
                  )}
                </div>

                {/* Action Footer */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto' }}>
                  <div style={{ display: 'flex', gap: '0.45rem' }}>
                    <Link
                      href={`/terminal?asset=${item.topic.slug}&tab=market`}
                      className="btn btn-primary"
                      style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem' }}
                    >
                      📈 Inspect Chart & Agents
                    </Link>
                    <Link
                      href={`/terminal?asset=${item.topic.slug}&tab=backtest`}
                      className="btn btn-outline"
                      style={{ padding: '0.35rem 0.7rem', fontSize: '0.78rem' }}
                    >
                      🧪 Backtest
                    </Link>
                  </div>

                  <button
                    onClick={() => handleRemoveAsset(item.topic.slug)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      fontSize: '0.76rem',
                    }}
                  >
                    Remove
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 4. CURATED PORTFOLIO NEWS & SOCIAL SIGNALS */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 800 }}>
              📰 Curated Intelligence Stream for Your Watched Portfolio
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Filtered multi-agent headlines and social catalysts strictly matching your watched tickers.
            </p>
          </div>
          <Link href="/terminal" style={{ fontSize: '0.82rem', color: 'var(--accent-cyan)', fontWeight: 600 }}>
            View All 297 Signals in Terminal →
          </Link>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '0.85rem' }}>
          {portfolioFeed.map(({ ticker, slug, post }, idx) => (
            <div
              key={`${post.external_id}_${idx}`}
              style={{
                padding: '0.85rem 1rem',
                borderRadius: '8px',
                backgroundColor: 'rgba(12, 18, 32, 0.75)',
                border: '1px solid var(--border-color)',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.4rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Link
                  href={`/terminal?asset=${slug}`}
                  style={{ fontWeight: 800, fontSize: '0.78rem', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}
                >
                  [{ticker}] • {post.source.toUpperCase()}
                </Link>
                <span
                  className="terminal-badge"
                  style={{
                    backgroundColor:
                      post.sentiment_label === 'positive'
                        ? 'rgba(16, 185, 129, 0.16)'
                        : post.sentiment_label === 'negative'
                        ? 'rgba(244, 63, 94, 0.16)'
                        : 'rgba(148, 163, 184, 0.15)',
                    color:
                      post.sentiment_label === 'positive'
                        ? '#34d399'
                        : post.sentiment_label === 'negative'
                        ? '#fb7185'
                        : '#cbd5e1',
                  }}
                >
                  {post.sentiment_score >= 0 ? `+${post.sentiment_score}` : post.sentiment_score}
                </span>
              </div>
              <a
                href={post.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: '0.88rem', fontWeight: 600, color: '#f1f5f9' }}
              >
                {post.title} ↗
              </a>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

