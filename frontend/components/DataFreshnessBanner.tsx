'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

interface DataFreshnessBannerProps {
  lastUpdated: string
  dataSource?: 'supabase' | 'snapshot_fallback' | string
  isRefreshing?: boolean
  onRefresh?: () => Promise<void> | void
  refreshLabel?: string
}

const ONE_HOUR_MS = 60 * 60 * 1000

function formatDateTime(iso: string): string {
  const dt = new Date(iso)
  if (Number.isNaN(dt.getTime())) return iso
  return dt.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatAgeLabel(ageMs: number): string {
  if (ageMs < 60_000) return 'just now'
  const mins = Math.floor(ageMs / 60_000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ${mins % 60}m ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ${hrs % 24}h ago`
}

export default function DataFreshnessBanner({
  lastUpdated,
  dataSource = 'supabase',
  isRefreshing: externalRefreshing,
  onRefresh,
  refreshLabel = 'Refresh Data Now',
}: DataFreshnessBannerProps) {
  const router = useRouter()
  const [nowMs, setNowMs] = useState<number>(() => Date.now())
  const [dismissedForTimestamp, setDismissedForTimestamp] = useState<string | null>(null)
  const [internalRefreshing, setInternalRefreshing] = useState<boolean>(false)
  const [refreshError, setRefreshError] = useState<string | null>(null)

  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), 30_000)
    return () => clearInterval(timer)
  }, [])

  const parsedMs = new Date(lastUpdated).getTime()
  const ageMs = Number.isNaN(parsedMs) ? 0 : Math.max(0, nowMs - parsedMs)
  const isStale = ageMs > ONE_HOUR_MS
  const isAccepted = dismissedForTimestamp === lastUpdated
  const refreshing = externalRefreshing ?? internalRefreshing

  async function handleRefreshClick() {
    setRefreshError(null)
    if (onRefresh) {
      await onRefresh()
      return
    }
    setInternalRefreshing(true)
    try {
      const res = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: 'ALL' }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.message || `Refresh failed (${res.status})`)
      }
      router.refresh()
    } catch (err: any) {
      setRefreshError(err?.message || 'Unable to refresh data right now.')
    } finally {
      setInternalRefreshing(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', marginBottom: '1.25rem' }}>
      {/* Always-visible timestamp & source strip */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '0.75rem',
          padding: '0.6rem 1rem',
          borderRadius: '10px',
          background: 'rgba(15, 23, 42, 0.72)',
          border: '1px solid rgba(148, 163, 184, 0.18)',
          fontSize: '0.82rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '999px',
              backgroundColor: isStale ? '#f59e0b' : '#10b981',
              display: 'inline-block',
            }}
          />
          <span style={{ color: 'var(--text-secondary)' }}>
            Data last updated on:{' '}
            <strong style={{ color: '#f8fafc', fontFamily: 'var(--font-mono)' }}>
              {formatDateTime(lastUpdated)}
            </strong>
          </span>
          <span
            className="terminal-badge"
            style={{
              fontSize: '0.72rem',
              padding: '0.12rem 0.45rem',
              backgroundColor: isStale ? 'rgba(245, 158, 11, 0.14)' : 'rgba(16, 185, 129, 0.14)',
              color: isStale ? '#fbbf24' : '#34d399',
            }}
          >
            {formatAgeLabel(ageMs)}
          </span>
        </div>

        <span
          className="terminal-badge"
          style={{
            fontSize: '0.72rem',
            padding: '0.14rem 0.5rem',
            backgroundColor:
              dataSource === 'supabase' ? 'rgba(6, 182, 212, 0.14)' : 'rgba(148, 163, 184, 0.14)',
            color: dataSource === 'supabase' ? '#38bdf8' : '#cbd5e1',
          }}
        >
          {dataSource === 'supabase' ? '🗄️ Loaded from Supabase DB' : '📦 Offline Snapshot Cache'}
        </span>
      </div>

      {/* > 1 Hour Staleness Notification Banner */}
      {isStale && !isAccepted && (
        <div
          role="status"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '1rem',
            padding: '0.85rem 1.15rem',
            borderRadius: '10px',
            background: 'linear-gradient(90deg, rgba(245, 158, 11, 0.14), rgba(15, 23, 42, 0.92))',
            border: '1px solid rgba(245, 158, 11, 0.45)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
            <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#fcd34d' }}>
              ⚠️ Data Refresh Needed (Older than 1 Hour)
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Current market &amp; sentiment signals were last updated on{' '}
              <strong style={{ color: '#f8fafc' }}>{formatDateTime(lastUpdated)}</strong>. You can
              trigger a fresh multi-agent scan or keep viewing the current dataset.
            </div>
            {refreshError && (
              <div style={{ fontSize: '0.78rem', color: '#fb7185', marginTop: '0.2rem' }}>
                {refreshError}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={handleRefreshClick}
              disabled={refreshing}
              className="btn btn-primary"
              style={{ padding: '0.45rem 0.95rem', fontSize: '0.8rem' }}
            >
              {refreshing ? '⏳ Refreshing...' : `🔄 ${refreshLabel}`}
            </button>
            <button
              type="button"
              onClick={() => setDismissedForTimestamp(lastUpdated)}
              disabled={refreshing}
              className="btn btn-outline"
              style={{ padding: '0.45rem 0.85rem', fontSize: '0.8rem' }}
            >
              ✓ Keep Current Data
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
