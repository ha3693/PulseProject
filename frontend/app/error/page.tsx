import Link from 'next/link'

export default function ErrorPage({
  searchParams,
}: {
  searchParams: { message?: string }
}) {
  return (
    <div className="container" style={{ paddingTop: '6rem', paddingBottom: '6rem', textAlign: 'center' }}>
      <div
        className="card"
        style={{
          maxWidth: '480px',
          margin: '0 auto',
          padding: '3rem 2rem',
          backgroundColor: 'var(--bg-secondary)',
        }}
      >
        <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⚠️</div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: '0.75rem' }}>
          Authentication Error
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', marginBottom: '2rem' }}>
          {searchParams?.message || 'Something went wrong during authentication. Please check your credentials and try again.'}
        </p>

        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
          <Link href="/login" className="btn btn-primary">
            Back to Sign In
          </Link>
          <Link href="/" className="btn btn-outline">
            Return Home
          </Link>
        </div>
      </div>
    </div>
  )
}

