'use client'

import React, { useState, useEffect, useMemo } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AssetSignal } from './PulseTerminal'

interface WatchlistViewProps {
  userEmail: string
  assets: AssetSignal[]
  initialWatchlistSlugs: string[]
}

export default function WatchlistView({
  userEmail,
  assets,
  initialWatchlistSlugs,
}: WatchlistViewProps) {
  const router = useRouter()
  const [watchlistSlugs, setWatchlistSlugs] = useState<string[]>(initialWatchlistSlugs)
  const [selectedAddSlug, setSelectedAddSlug] = useState<string>('')
  const [toastMsg, setToastMsg] = useState<string | null>(null)

  useEffect(() => {
    setWatchlistSlugs(initialWatchlistSlugs)
  }, [initialWatchlistSlugs])

  useEffect(() => {
    let active = true
    async function syncWatchlist() {
      try {
        const res = await fetch('/api/watchlist', { cache: 'no-store' })
        if (!res.ok) return
        const data = await res.json()
        if (active && data?.authenticated && Array.isArray(data.items)) {
          const slugs = data.items
            .map((item: any) => item.topic?.slug)
            .filter(Boolean)
          setWatchlistSlugs(slugs)
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

  const watchedAssets = useMemo(
    () => assets.filter((a) => watchlistSlugs.includes(a.topic.slug)),
    [assets, watchlistSlugs]
  )

  const unwatchedAssets = useMemo(
    () => assets.filter((a) => !watchlistSlugs.includes(a.topic.slug)),
    [assets, watchlistSlugs]
  )

  useEffect(() => {
    if (unwatchedAssets.length > 0 && (!selectedAddSlug || watchlistSlugs.includes(selectedAddSlug))) {
      setSelectedAddSlug(unwatchedAssets[0].topic.slug)
    }
  }, [unwatchedAssets, watchlistSlugs, selectedAddSlug])

  async function handleAdd(slug: string) {
    if (!slug || watchlistSlugs.includes(slug)) return
    setWatchlistSlugs((prev) => [...prev, slug])
    setToastMsg(`Added ${slug.toUpperCase()} to Watchlist`)
    setTimeout(() => setToastMsg(null), 3000)

    try {
      await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug }),
      })
      window.dispatchEvent(new CustomEvent('pulse-watchlist-updated'))
      router.refresh()
    } catch {
      // Optimistic state updated
    }
  }

  async function handleRemove(slug: string) {
    setWatchlistSlugs((prev) => prev.filter((s) => s !== slug))
    setToastMsg(`Removed ${slug.toUpperCase()} from Watchlist`)
    setTimeout(() => setToastMsg(null), 3000)

    try {
      await fetch(`/api/watchlist?slug=${encodeURIComponent(slug)}`, { method: 'DELETE' })
      window.dispatchEvent(new CustomEvent('pulse-watchlist-updated'))
      router.refresh()
    } catch {
      // Optimistic state updated
    }
  }

  return (
    <div className="container" style={{ paddingTop: '2.5rem', paddingBottom: '4rem' }}>
      {toastMsg && (
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
          <span>✅ {toastMsg}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#34d399' }}>
            Synced across Watchlist, Dashboard & Terminal
          </span>
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
        <div>
          <span className="brand-badge">Supabase Row-Level Security (RLS)</span>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.35rem' }}>
            ★ My Multi-Asset Watchlist ({watchedAssets.length})
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Authenticated as <span style={{ color: 'var(--accent-cyan)' }}>{userEmail}</span> • Real-time divergence monitoring across your tracked portfolio.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {unwatchedAssets.length > 0 && (
            <>
              <select
                value={selectedAddSlug}
                onChange={(e) => setSelectedAddSlug(e.target.value)}
                style={{
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  backgroundColor: 'var(--bg-secondary)',
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
                onClick={() => handleAdd(selectedAddSlug || unwatchedAssets[0]?.topic.slug)}
                className="btn btn-primary"
                style={{ padding: '0.5rem 0.95rem', fontSize: '0.84rem' }}
              >
                + Add Stock
              </button>
            </>
          )}
          <Link href="/dashboard" className="btn btn-outline" style={{ padding: '0.5rem 0.95rem', fontSize: '0.84rem' }}>
            My Dashboard →
          </Link>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(330px, 1fr))', gap: '1.25rem' }}>
        {watchedAssets.map((item) => (
          <div key={item.topic.slug} className="card" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '1.25rem', fontWeight: 800 }}>{item.topic.ticker}</span>
                  <span className="brand-badge">{item.top_drivers?.sector || item.topic.category}</span>
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{item.topic.name}</div>
              </div>

              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '1.2rem', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
                  ${item.latest_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </div>
                <div
                  style={{
                    fontSize: '0.8rem',
                    fontFamily: 'var(--font-mono)',
                    color: item.price_change_pct >= 0 ? '#34d399' : '#fb7185',
                  }}
                >
                  {item.price_change_pct >= 0 ? '+' : ''}
                  {item.price_change_pct}%
                </div>
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '0.65rem 0.85rem',
                borderRadius: '8px',
                backgroundColor: 'rgba(15, 23, 42, 0.65)',
                border: '1px solid var(--border-color)',
              }}
            >
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Pulse Sentiment Index</div>
                <div
                  style={{
                    fontSize: '1.3rem',
                    fontWeight: 800,
                    fontFamily: 'var(--font-mono)',
                    color: item.pulse_index >= 0 ? '#34d399' : '#fb7185',
                  }}
                >
                  {item.pulse_index >= 0 ? `+${item.pulse_index}` : item.pulse_index}
                </div>
              </div>

              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>FinBERT Benchmark</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#c084fc' }}>
                  {item.finbert_index >= 0 ? `+${item.finbert_index}` : item.finbert_index}
                </div>
              </div>
            </div>

            <p style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {item.synthesis}
            </p>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto', paddingTop: '0.35rem' }}>
              <Link
                href={`/terminal?asset=${item.topic.slug}&tab=market`}
                className="btn btn-primary"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem' }}
              >
                📈 Inspect in Terminal →
              </Link>
              <button
                onClick={() => handleRemove(item.topic.slug)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  fontSize: '0.78rem',
                }}
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

