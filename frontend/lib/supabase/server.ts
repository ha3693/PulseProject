import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

const DEFAULT_SUPABASE_URL = 'https://nawxvorojsgwdrgksdmu.supabase.co'
const DEFAULT_SUPABASE_PUBLIC_KEY = 'sb_publishable_ZcuaJDOz6CVaPJ61R3RoyA_DRi_TV2c'

export async function createClient() {
  const cookieStore = await cookies()

  const supabaseUrl =
    process.env.NEXT_PUBLIC_SUPABASE_URL ||
    process.env.SUPABASE_URL ||
    DEFAULT_SUPABASE_URL

  const supabaseKey =
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    DEFAULT_SUPABASE_PUBLIC_KEY

  return createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll()
      },
      setAll(cookiesToSet: { name: string; value: string; options?: any }[]) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          )
        } catch {
          // Can be ignored when called from a Server Component
        }
      },
    },
  })
}
