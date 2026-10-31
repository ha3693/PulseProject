import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { revalidatePath } from 'next/cache'

export default async function AccountPage({
  searchParams,
}: {
  searchParams: { message?: string }
}) {
  const supabase = await createClient()

  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login?redirectTo=/account')
  }

  const { data: profile } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single()

  async function updateProfile(formData: FormData) {
    'use server'
    const supabase = await createClient()
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      redirect('/login')
    }

    const fullName = formData.get('fullName') as string

    await supabase.from('profiles').upsert({
      id: user.id,
      email: user.email,
      full_name: fullName,
      updated_at: new Date().toISOString(),
    })

    revalidatePath('/account')
    redirect('/account?message=Profile updated successfully')
  }

  return (
    <div className="container" style={{ paddingTop: '3rem', paddingBottom: '5rem' }}>
      <div
        className="card"
        style={{
          maxWidth: '560px',
          margin: '0 auto',
          backgroundColor: 'var(--bg-secondary)',
        }}
      >
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: '0.5rem' }}>
          Account Settings
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '2rem' }}>
          Manage your personal profile and authentication settings.
        </p>

        {searchParams?.message && (
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

        <form action={updateProfile} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
              User ID
            </label>
            <input
              type="text"
              value={user.id}
              disabled
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-muted)',
                fontSize: '0.85rem',
                fontFamily: 'var(--font-mono)',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
              Email address
            </label>
            <input
              type="email"
              value={user.email || ''}
              disabled
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-muted)',
                fontSize: '0.9rem',
              }}
            />
          </div>

          <div>
            <label htmlFor="fullName" style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
              Full Name
            </label>
            <input
              id="fullName"
              name="fullName"
              type="text"
              defaultValue={profile?.full_name || ''}
              placeholder="Your Name"
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

          <button type="submit" className="btn btn-primary" style={{ marginTop: '0.5rem', padding: '0.75rem' }}>
            Save Changes
          </button>
        </form>

        <hr style={{ borderColor: 'var(--border-color)', margin: '2rem 0' }} />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>Sign out of session</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Clear server and client auth cookies</div>
          </div>
          <form action="/auth/signout" method="post">
            <button type="submit" className="btn btn-outline" style={{ color: 'var(--accent-rose)' }}>
              Sign Out
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

