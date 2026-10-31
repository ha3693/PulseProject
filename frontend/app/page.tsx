import Link from 'next/link'
import { loadPulseTerminalData } from '@/lib/data/loadPulseData'
import { AssetSignal } from '@/components/PulseTerminal'

export const dynamic = 'force-dynamic'

export default async function HomePage() {
  const { snapshot, user } = await loadPulseTerminalData()
  const assets: AssetSignal[] = snapshot?.assets || []

  const sortedByBullish = [...assets].sort((a, b) => b.pulse_index - a.pulse_index)
  const topBullish = sortedByBullish.slice(0, 4)
  const topBearish = [...assets].sort((a, b) => a.pulse_index - b.pulse_index).slice(0, 4)
  const divergenceAssets = assets.filter(
    (a) => a.divergence_flag || a.history.slice(-5).some((h) => h.divergence_flag)
  )

  const avgMarketPulse =
    assets.length > 0
      ? (assets.reduce((acc, a) => acc + a.pulse_index, 0) / assets.length).toFixed(1)
      : '0.0'
  const totalPosts = assets.reduce((acc, a) => acc + a.total_volume, 0)

  return (
    <div>
      {/* LIVE TICKER RIBBON */}
      <div className="ticker-tape-wrap">
        <div
          className="container"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.65rem',
            overflowX: 'auto',
            padding: '0.55rem 1rem',
          }}
        >
          <span className="live-dot-pill">
            <span className="pulse-dot" /> LIVE MARKET PULSE
          </span>
          {assets.map((item) => (
            <Link
              key={item.topic.slug}
              href={`/terminal?asset=${item.topic.slug}`}
              className="ticker-chip"
            >
              <span style={{ fontWeight: 700, color: '#f8fafc' }}>{item.topic.ticker}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: '#cbd5e1' }}>
                ${item.latest_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
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
                  backgroundColor:
                    item.pulse_index >= 15
                      ? 'rgba(16, 185, 129, 0.16)'
                      : item.pulse_index <= -15
                      ? 'rgba(244, 63, 94, 0.16)'
                      : 'rgba(6, 182, 212, 0.14)',
                  color:
                    item.pulse_index >= 15 ? '#34d399' : item.pulse_index <= -15 ? '#fb7185' : '#38bdf8',
                }}
              >
                {item.pulse_index >= 0 ? `+${item.pulse_index}` : item.pulse_index}
              </span>
            </Link>
          ))}
        </div>
      </div>

      <div className="container" style={{ paddingTop: '2.75rem', paddingBottom: '4.5rem' }}>
        {/* 1. EXECUTIVE HERO BANNER */}
        <div
          className="card"
          style={{
            padding: '2.5rem 2.25rem',
            marginBottom: '2rem',
            background:
              'radial-gradient(circle at 90% 20%, rgba(6, 182, 212, 0.18), rgba(16, 24, 41, 0.94) 60%)',
            border: '1px solid rgba(6, 182, 212, 0.35)',
          }}
        >
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '2rem',
            }}
          >
            <div style={{ maxWidth: '720px' }}>
              <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', marginBottom: '0.85rem' }}>
                <span className="live-dot-pill">
                  <span className="pulse-dot" /> 8 AI AGENTS ACTIVE
                </span>
                <span className="brand-badge">FinBERT + LLM Hybrid Calibration</span>
                <span className="brand-badge">Supabase pg_cron (Every 6h)</span>
              </div>

              <h1
                style={{
                  fontSize: '2.55rem',
                  fontWeight: 800,
                  letterSpacing: '-0.03em',
                  lineHeight: 1.15,
                  marginBottom: '1rem',
                }}
              >
                Institutional Market Signals &{' '}
                <span style={{ color: 'var(--accent-cyan)' }}>Real-Time Sentiment Heatmap</span>
              </h1>
              <p style={{ color: 'var(--text-secondary)', fontSize: '1.02rem', marginBottom: '1.6rem' }}>
                Pulse synthesizes breaking coverage across Yahoo Finance, GDELT DOC 2.0, Reddit, StockTwits,
                and Bluesky into source-cited sentiment indices, price-sentiment divergence flags, and
                competitor share-of-voice analytics.
              </p>

              <div style={{ display: 'flex', gap: '0.85rem', flexWrap: 'wrap' }}>
                <Link href="/terminal" className="btn btn-primary" style={{ padding: '0.7rem 1.4rem', fontSize: '0.92rem' }}>
                  ⚡ Open Interactive Terminal →
                </Link>
                {user ? (
                  <Link href="/dashboard" className="btn btn-outline" style={{ padding: '0.7rem 1.4rem', fontSize: '0.92rem' }}>
                    ★ Go to My Personal Dashboard ({user.email?.split('@')[0]})
                  </Link>
                ) : (
                  <Link href="/login" className="btn btn-outline" style={{ padding: '0.7rem 1.4rem', fontSize: '0.92rem' }}>
                    🔒 Sign In to Personal Dashboard
                  </Link>
                )}
                <Link href="/terminal?tab=brand" className="btn btn-outline" style={{ padding: '0.7rem 1.2rem', fontSize: '0.92rem' }}>
                  🏷️ Brand Lens (Nike vs. Adidas)
                </Link>
              </div>
            </div>

            {/* Global Macro Telemetry Box */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '0.85rem',
                minWidth: '300px',
              }}
            >
              <div
                style={{
                  padding: '1rem',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(6, 9, 17, 0.75)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Composite Market Index
                </div>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#34d399', fontFamily: 'var(--font-mono)' }}>
                  +{avgMarketPulse}
                </div>
                <div style={{ fontSize: '0.73rem', color: 'var(--text-secondary)' }}>Across 14 Core Assets</div>
              </div>

              <div
                style={{
                  padding: '1rem',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(6, 9, 17, 0.75)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Divergence Signals
                </div>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fbbf24', fontFamily: 'var(--font-mono)' }}>
                  {divergenceAssets.length} ⚡
                </div>
                <div style={{ fontSize: '0.73rem', color: 'var(--text-secondary)' }}>5-Day Active Window</div>
              </div>

              <div
                style={{
                  padding: '1rem',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(6, 9, 17, 0.75)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Verified Citations
                </div>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
                  {totalPosts}
                </div>
                <div style={{ fontSize: '0.73rem', color: 'var(--text-secondary)' }}>Scored by FinBERT</div>
              </div>

              <div
                style={{
                  padding: '1rem',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(6, 9, 17, 0.75)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Historical Depth
                </div>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#c084fc', fontFamily: 'var(--font-mono)' }}>
                  420 Bars
                </div>
                <div style={{ fontSize: '0.73rem', color: 'var(--text-secondary)' }}>Synced in Supabase</div>
              </div>
            </div>
          </div>
        </div>

        {/* 2. LIVE SECTOR & ASSET SENTIMENT HEATMAP */}
        <div className="card" style={{ marginBottom: '2rem' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '1.15rem',
              flexWrap: 'wrap',
              gap: '0.75rem',
            }}
          >
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800 }}>
                🔥 Real-Time Multi-Asset Sentiment Heatmap
              </h2>
              <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
                Click any asset tile to launch its interactive dual-axis chart, 5-agent consensus, and backtesting lab in the Terminal.
              </p>
            </div>
            <Link href="/terminal" style={{ fontSize: '0.84rem', color: 'var(--accent-cyan)', fontWeight: 600 }}>
              Open Full Workstation →
            </Link>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(185px, 1fr))',
              gap: '0.85rem',
            }}
          >
            {assets.map((item) => {
              const s = item.pulse_index
              const bg =
                s >= 28
                  ? 'linear-gradient(145deg, rgba(16, 185, 129, 0.28), rgba(6, 78, 59, 0.35))'
                  : s >= 12
                  ? 'linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(15, 23, 42, 0.8))'
                  : s <= -10
                  ? 'linear-gradient(145deg, rgba(244, 63, 94, 0.25), rgba(76, 5, 25, 0.35))'
                  : 'linear-gradient(145deg, rgba(6, 182, 212, 0.14), rgba(15, 23, 42, 0.8))'

              const borderCol =
                s >= 15
                  ? 'rgba(16, 185, 129, 0.45)'
                  : s <= -10
                  ? 'rgba(244, 63, 94, 0.45)'
                  : 'rgba(6, 182, 212, 0.35)'

              return (
                <Link
                  key={item.topic.slug}
                  href={`/terminal?asset=${item.topic.slug}`}
                  style={{
                    padding: '1rem',
                    borderRadius: '10px',
                    background: bg,
                    border: `1px solid ${borderCol}`,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '0.6rem',
                    transition: 'transform 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 800, fontSize: '1.05rem' }}>{item.topic.ticker}</span>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 800,
                        fontSize: '0.9rem',
                        color: s >= 12 ? '#34d399' : s <= -10 ? '#fb7185' : '#38bdf8',
                      }}
                    >
                      {s >= 0 ? `+${s}` : s}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.76rem', color: '#cbd5e1', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {item.topic.name}
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.78rem',
                      fontFamily: 'var(--font-mono)',
                      paddingTop: '0.35rem',
                      borderTop: '1px solid rgba(255,255,255,0.08)',
                    }}
                  >
                    <span>${item.latest_price.toLocaleString()}</span>
                    <span style={{ color: item.price_change_pct >= 0 ? '#34d399' : '#fb7185' }}>
                      {item.price_change_pct >= 0 ? '+' : ''}
                      {item.price_change_pct}%
                    </span>
                  </div>
                </Link>
              )
            })}
          </div>
        </div>

        {/* 3. THREE-COLUMN MARKET RADAR: BULLISH LEADERS, CONTRARIAN / BEARISH, DIVERGENCES */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1.25rem' }}>
          <div className="card" style={{ borderTop: '3px solid #10b981' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#34d399', marginBottom: '0.85rem' }}>
              🚀 Top Bullish Conviction Leaders
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {topBullish.map((item) => (
                <Link
                  key={item.topic.slug}
                  href={`/terminal?asset=${item.topic.slug}`}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.65rem 0.8rem',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(15, 23, 42, 0.65)',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                      {item.topic.ticker} — {item.topic.name}
                    </div>
                    <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                      {item.top_drivers.sector} • FinBERT: +{item.finbert_index}
                    </div>
                  </div>
                  <span className="terminal-badge badge-bullish">+{item.pulse_index}</span>
                </Link>
              ))}
            </div>
          </div>

          <div className="card" style={{ borderTop: '3px solid #f43f5e' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#fb7185', marginBottom: '0.85rem' }}>
              ⚠️ Cautious / Contrarian Sentiment Watch
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {topBearish.map((item) => (
                <Link
                  key={item.topic.slug}
                  href={`/terminal?asset=${item.topic.slug}`}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.65rem 0.8rem',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(15, 23, 42, 0.65)',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                      {item.topic.ticker} — {item.topic.name}
                    </div>
                    <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                      {item.top_drivers.sector} • FinBERT: {item.finbert_index >= 0 ? `+${item.finbert_index}` : item.finbert_index}
                    </div>
                  </div>
                  <span
                    className="terminal-badge"
                    style={{
                      backgroundColor: item.pulse_index < 0 ? 'rgba(244, 63, 94, 0.16)' : 'rgba(6, 182, 212, 0.14)',
                      color: item.pulse_index < 0 ? '#fb7185' : '#38bdf8',
                    }}
                  >
                    {item.pulse_index >= 0 ? `+${item.pulse_index}` : item.pulse_index}
                  </span>
                </Link>
              ))}
            </div>
          </div>

          <div className="card" style={{ borderTop: '3px solid #fbbf24' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#fbbf24', marginBottom: '0.85rem' }}>
              ⚡ Price vs. Sentiment Divergence Radar
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {divergenceAssets.slice(0, 4).map((item) => (
                <Link
                  key={item.topic.slug}
                  href={`/terminal?asset=${item.topic.slug}&tab=backtest`}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.65rem 0.8rem',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(15, 23, 42, 0.65)',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                      {item.topic.ticker} — {item.topic.name}
                    </div>
                    <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                      Click to inspect divergence alpha in Backtest Lab
                    </div>
                  </div>
                  <span
                    className="terminal-badge"
                    style={{
                      backgroundColor: 'rgba(245, 158, 11, 0.18)',
                      color: '#fbbf24',
                      border: '1px solid rgba(245, 158, 11, 0.35)',
                    }}
                  >
                    ⚡ DIV ALERT
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
