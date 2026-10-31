import { createBrowserClient } from '@supabase/ssr'

const DEFAULT_SUPABASE_URL = 'https://nawxvorojsgwdrgksdmu.supabase.co'
const DEFAULT_SUPABASE_PUBLIC_KEY = 'sb_publishable_ZcuaJDOz6CVaPJ61R3RoyA_DRi_TV2c'

export function createClient() {
  const supabaseUrl =
    process.env.NEXT_PUBLIC_SUPABASE_URL ||
    DEFAULT_SUPABASE_URL

  const supabaseKey =
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    DEFAULT_SUPABASE_PUBLIC_KEY

  return createBrowserClient(supabaseUrl, supabaseKey)
}
