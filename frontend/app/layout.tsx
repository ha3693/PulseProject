import type { Metadata } from 'next'
import Link from 'next/link'
import './globals.css'
import { createClient } from '@/lib/supabase/server'

export const metadata: Metadata = {
  title: 'Pulse — Real-Time Sentiment & Market Signal Intelligence Platform',
  description: 'Multi-Agent AI & FinBERT Market Signals, Brand Lens Share-of-Voice, Divergence Detection, and Backtesting.',
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  let user: any = null
  try {
    const supabase = await createClient()
    const { data } = await supabase.auth.getUser()
    user = data?.user || null
  } catch {
    // Fallback
  }

  return (
    <html lang="en">
      <body>
        <header className="navbar">
          <div className="container nav-content">
            <Link href="/" className="nav-brand">
              <span style={{ color: 'var(--accent-cyan)' }}>⚡ PULSE</span>
              <span className="brand-badge">Multi-Agent Sentiment Platform</span>
            </Link>

            <nav className="nav-links">
              <Link href="/">Market Overview</Link>
              <Link href="/terminal">Deep-Dive Terminal</Link>
              <Link href="/dashboard">My Dashboard</Link>
              <Link href="/watchlist">Watchlist</Link>
              {user ? (
                <>
                  <Link href="/account" style={{ color: '#38bdf8', fontWeight: 600 }}>
                    {user.email?.split('@')[0]}
                  </Link>
                  <form action="/auth/signout" method="post">
                    <button type="submit" className="btn btn-outline" style={{ padding: '0.32rem 0.75rem', fontSize: '0.8rem' }}>
                      Sign Out
                    </button>
                  </form>
                </>
              ) : (
                <Link href="/login" className="btn btn-primary" style={{ padding: '0.35rem 0.9rem', fontSize: '0.82rem' }}>
                  Sign In / Register
                </Link>
              )}
            </nav>
          </div>
        </header>

        <main>{children}</main>
      </body>
    </html>
  )
}
