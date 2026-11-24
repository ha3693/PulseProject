'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

interface DataFreshnessBannerProps {
  lastUpdated: string
  dataSource?: 'supabase' | 'snapshot_fallback' | string
  initialIsRefreshing?: boolean
  isRefreshing?: boolean
  onRefresh?: () => Promise<void> | void
  onRefreshComplete?: (payload?: any) => void
  refreshLabel?: string
  refreshTopic?: string
  refreshMode?: 'prices_only' | 'full'
}

const ONE_HOUR_MS = 60 * 60 * 1000
const REFRESH_STORAGE_KEY = 'pulse_refresh_in_progress'
const DISMISS_STORAGE_KEY = 'pulse_dismissed_ts'

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
  initialIsRefreshing = false,
  isRefreshing: externalRefreshing,
  onRefresh,
  onRefreshComplete,
  refreshLabel = 'Refresh Data Now',
  refreshTopic = 'ALL',
  refreshMode = 'prices_only',
}: DataFreshnessBannerProps) {
  const router = useRouter()
  const [nowMs, setNowMs] = useState<number>(() => Date.now())
  const [dismissedForTimestamp, setDismissedForTimestamp] = useState<string | null>(null)
  const [internalRefreshing, setInternalRefreshing] = useState<boolean>(initialIsRefreshing)
  const [justCompletedMsg, setJustCompletedMsg] = useState<string | null>(null)
  const [refreshError, setRefreshError] = useState<string | null>(null)

  // Restore cross-page session state on mount
  useEffect(() => {
    try {
      const savedDismissed = sessionStorage.getItem(DISMISS_STORAGE_KEY)
      if (savedDismissed) setDismissedForTimestamp(savedDismissed)

      const savedRefresh = sessionStorage.getItem(REFRESH_STORAGE_KEY)
      if (savedRefresh) {
        const parsed = JSON.parse(savedRefresh)
        if (parsed?.startedAt && Date.now() - parsed.startedAt < 10 * 60 * 1000) {
          setInternalRefreshing(true)
        } else {
          sessionStorage.removeItem(REFRESH_STORAGE_KEY)
        }
      }
    } catch {
      // Ignore storage errors
    }
  }, [])

  useEffect(() => {
    if (initialIsRefreshing) {
      setInternalRefreshing(true)
    }
  }, [initialIsRefreshing])

  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), 30_000)
    return () => clearInterval(timer)
  }, [])

  const refreshing = Boolean(externalRefreshing || internalRefreshing)

  // Poll GET /api/ingest while a refresh is in progress so navigating across pages stays in sync
  useEffect(() => {
    if (!refreshing) return
    let active = true

    const pollStatus = async () => {
      try {
        const res = await fetch('/api/ingest', { cache: 'no-store' })
        if (!res.ok || !active) return
        const data = await res.json()

        // Wait until backend reports no active running job
        if (data?.isRunning === false) {
          let startedAt = 0
          try {
            const raw = sessionStorage.getItem(REFRESH_STORAGE_KEY)
            startedAt = raw ? JSON.parse(raw)?.startedAt || 0 : 0
          } catch {
            startedAt = 0
          }

          const latestTs = Math.max(
            data?.latestCompletedAt ? new Date(data.latestCompletedAt).getTime() : 0,
            data?.snapshotGeneratedAt ? new Date(data.snapshotGeneratedAt).getTime() : 0
          )
          // Finish only when a new completed run/snapshot arrived (or no startedAt tracked)
          if (!startedAt || latestTs > startedAt - 5000) {
            try {
              sessionStorage.removeItem(REFRESH_STORAGE_KEY)
              sessionStorage.removeItem(DISMISS_STORAGE_KEY)
            } catch {
              // Ignore
            }
            if (!active) return
            setInternalRefreshing(false)
            setJustCompletedMsg(
              data?.dbSynced === false
                ? 'Refresh finished (saved to local snapshot; check SUPABASE_ACCESS_TOKEN in .env to sync DB).'
                : 'Fresh market & sentiment data saved to database. Updating view...'
            )
            if (onRefreshComplete) {
              onRefreshComplete(data)
            }
            router.refresh()
            setTimeout(() => {
              if (active) setJustCompletedMsg(null)
            }, 6000)
          }
        }
      } catch {
        // Keep polling on transient error
      }
    }

    const interval = setInterval(pollStatus, 4000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [refreshing, onRefreshComplete, router])

  const parsedMs = new Date(lastUpdated).getTime()
  const ageMs = Number.isNaN(parsedMs) ? 0 : Math.max(0, nowMs - parsedMs)
  const isStale = ageMs > ONE_HOUR_MS
  const isAccepted = dismissedForTimestamp === lastUpdated

  function handleAcceptCurrent() {
    setDismissedForTimestamp(lastUpdated)
    try {
      sessionStorage.setItem(DISMISS_STORAGE_KEY, lastUpdated)
    } catch {
      // Ignore
    }
  }

  async function handleRefreshClick() {
    setRefreshError(null)
    setJustCompletedMsg(null)
    try {
      sessionStorage.setItem(
        REFRESH_STORAGE_KEY,
        JSON.stringify({ startedAt: Date.now(), target: refreshLabel })
      )
    } catch {
      // Ignore
    }
    setInternalRefreshing(true)

    if (onRefresh) {
      await onRefresh()
      return
    }

    try {
      const res = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: refreshTopic, mode: refreshMode }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.message || `Refresh failed (${res.status})`)
      }
      const data = await res.json()
      if (data?.status === 'completed' && !data?.isRunning) {
        try {
          sessionStorage.removeItem(REFRESH_STORAGE_KEY)
          sessionStorage.removeItem(DISMISS_STORAGE_KEY)
        } catch {
          // Ignore
        }
        setInternalRefreshing(false)
        setJustCompletedMsg('Fresh data saved to database!')
        router.refresh()
      }
    } catch (err: any) {
      try {
        sessionStorage.removeItem(REFRESH_STORAGE_KEY)
      } catch {
        // Ignore
      }
      setInternalRefreshing(false)
      setRefreshError(err?.message || 'Unable to refresh data right now.')
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
              backgroundColor: refreshing ? '#38bdf8' : isStale ? '#f59e0b' : '#10b981',
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

      {/* Persistent Cross-Page "Refresh in Progress" Banner */}
      {refreshing && (
        <div
          role="status"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '0.85rem 1.15rem',
            borderRadius: '10px',
            background: 'linear-gradient(90deg, rgba(6, 182, 212, 0.18), rgba(15, 23, 42, 0.94))',
            border: '1px solid rgba(56, 189, 248, 0.45)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
            <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#7dd3fc' }}>
              ⏳ Data Refresh in Progress
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Our AI agents are gathering fresh market prices, news, and social sentiment and saving
              them to the shared database. You can switch pages freely—the app will update
              automatically as soon as it finishes.
            </div>
          </div>
          <span
            className="terminal-badge"
            style={{
              padding: '0.3rem 0.7rem',
              fontSize: '0.75rem',
              backgroundColor: 'rgba(56, 189, 248, 0.16)',
              color: '#38bdf8',
              fontFamily: 'var(--font-mono)',
            }}
          >
            SYNCING TO SUPABASE...
          </span>
        </div>
      )}

      {/* Completion Confirmation Banner */}
      {justCompletedMsg && !refreshing && (
        <div
          role="status"
          style={{
            padding: '0.75rem 1.1rem',
            borderRadius: '10px',
            background: 'rgba(16, 185, 129, 0.15)',
            border: '1px solid rgba(16, 185, 129, 0.45)',
            color: '#6ee7b7',
            fontSize: '0.85rem',
            fontWeight: 600,
          }}
        >
          ✅ {justCompletedMsg}
        </div>
      )}

      {/* > 1 Hour Staleness Notification Banner */}
      {!refreshing && !justCompletedMsg && isStale && !isAccepted && (
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
              <strong style={{ color: '#f8fafc' }}>{formatDateTime(lastUpdated)}</strong>. Refreshing
              will update the shared database for all users, or you can keep viewing the current data.
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
              className="btn btn-primary"
              style={{ padding: '0.45rem 0.95rem', fontSize: '0.8rem' }}
            >
              🔄 {refreshLabel}
            </button>
            <button
              type="button"
              onClick={handleAcceptCurrent}
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
