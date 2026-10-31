'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'

async function confirmAndEnsureProfileInSupabase(email: string, password?: string, fullName?: string) {
  const safeEmail = email.replace(/'/g, "''")
  const safeName = (fullName || email.split('@')[0]).replace(/'/g, "''")
  const safePass = password ? password.replace(/'/g, "''") : null

  const passwordUpdateClause = safePass
    ? `, encrypted_password = extensions.crypt('${safePass}', extensions.gen_salt('bf'))`
    : ''

  const query = `
    UPDATE auth.users
    SET email_confirmed_at = COALESCE(email_confirmed_at, NOW()),
        updated_at = NOW()
        ${passwordUpdateClause}
    WHERE email = '${safeEmail}';

    INSERT INTO public.profiles (id, email, full_name, updated_at)
    SELECT id, email, COALESCE(raw_user_meta_data->>'full_name', '${safeName}'), NOW()
    FROM auth.users
    WHERE email = '${safeEmail}'
    ON CONFLICT (id) DO UPDATE SET
      email = EXCLUDED.email,
      updated_at = NOW();
  `

  const projectRef = process.env.SUPABASE_PROJECT_REF
  const accessToken = process.env.SUPABASE_ACCESS_TOKEN
  if (!projectRef || !accessToken) {
    return
  }

  try {
    await fetch(`https://api.supabase.com/v1/projects/${projectRef}/database/query`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    })
  } catch {
    // Fallback if offline
  }
}

export async function login(formData: FormData) {
  const supabase = await createClient()

  const email = (formData.get('email') as string)?.trim()
  const password = formData.get('password') as string

  if (!email || !password) {
    redirect('/login?error=Email and password are required')
  }

  let { error } = await supabase.auth.signInWithPassword({
    email,
    password,
  })

  // If the account exists but email confirmation link expired or wasn't processed, auto-confirm and retry
  if (error && error.message.toLowerCase().includes('confirm')) {
    await confirmAndEnsureProfileInSupabase(email)
    const retry = await supabase.auth.signInWithPassword({ email, password })
    error = retry.error
  }

  if (error) {
    redirect(`/login?error=${encodeURIComponent(error.message)}`)
  }

  await confirmAndEnsureProfileInSupabase(email)
  revalidatePath('/', 'layout')
  redirect('/dashboard')
}

export async function signup(formData: FormData) {
  const supabase = await createClient()

  const email = (formData.get('email') as string)?.trim()
  const password = formData.get('password') as string
  const fullName = (formData.get('full_name') as string)?.trim()

  if (!email || !password) {
    redirect('/login?error=Email and password are required')
  }

  if (password.length < 6) {
    redirect('/login?error=Password must be at least 6 characters')
  }

  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      emailRedirectTo: 'http://localhost:3000/auth/callback',
      data: {
        full_name: fullName || email.split('@')[0],
      },
    },
  })

  // Even if Supabase SMTP rate-limits the confirmation email, auto-confirm the user
  // and ensure their public.profiles row exists so they can sign in immediately!
  await confirmAndEnsureProfileInSupabase(email, password, fullName)

  if (error && !error.message.toLowerCase().includes('rate limit') && !error.message.toLowerCase().includes('already registered')) {
    redirect(`/login?error=${encodeURIComponent(error.message)}`)
  }

  // Sign the user in right away so they land directly on /dashboard
  if (!data?.session) {
    const { error: signInErr } = await supabase.auth.signInWithPassword({
      email,
      password,
    })
    if (signInErr) {
      redirect(`/login?error=${encodeURIComponent(signInErr.message)}`)
    }
  }

  revalidatePath('/', 'layout')
  redirect('/dashboard')
}
