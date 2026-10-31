import { login, signup } from './actions'

export default function LoginPage({
  searchParams,
}: {
  searchParams: { message?: string; error?: string; redirectTo?: string }
}) {
  return (
    <div className="container" style={{ paddingTop: '5rem', paddingBottom: '5rem' }}>
      <div
        className="card"
        style={{
          maxWidth: '440px',
          margin: '0 auto',
          padding: '2.5rem',
          backgroundColor: 'var(--bg-secondary)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Welcome to Pulse
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Sign in or create an account to access real-time market sentiment & watchlists.
          </p>
        </div>

        {searchParams.error && (
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: '6px',
              backgroundColor: 'rgba(244, 63, 94, 0.15)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              color: 'var(--accent-rose)',
              fontSize: '0.875rem',
              marginBottom: '1.5rem',
            }}
          >
            {searchParams.error}
          </div>
        )}

        {searchParams.message && (
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: '6px',
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: 'var(--accent-emerald)',
              fontSize: '0.875rem',
              marginBottom: '1.5rem',
            }}
          >
            {searchParams.message}
          </div>
        )}

        <form style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div>
            <label
              htmlFor="email"
              style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}
            >
              Email address
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              placeholder="you@domain.com"
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
                outline: 'none',
              }}
            />
          </div>

          <div>
            <label
              htmlFor="password"
              style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}
            >
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              placeholder="••••••••"
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
                outline: 'none',
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              formAction={login}
              className="btn btn-primary"
              style={{ flex: 1, padding: '0.75rem' }}
            >
              Log In
            </button>
            <button
              formAction={signup}
              className="btn btn-outline"
              style={{ flex: 1, padding: '0.75rem' }}
            >
              Sign Up
            </button>
          </div>
        </form>

        <div style={{ marginTop: '2rem', textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Secured by Supabase Auth (Row-Level Security & Encrypted Cookies)
        </div>
      </div>
    </div>
  )
}

