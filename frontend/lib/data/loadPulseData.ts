import fs from 'fs'
import path from 'path'
import { createClient } from '@/lib/supabase/server'

export const DEFAULT_WATCHLIST_ITEMS = [
  { slug: 'nvda', notes: 'Core AI infrastructure holding — monitoring Blackwell ramp & options flow' },
  { slug: 'aapl', notes: 'Watching consumer upgrade cycle sentiment vs. services growth' },
  { slug: 'btc-usd', notes: 'Macro liquidity proxy & institutional ETF inflow tracker' },
  { slug: 'nike', notes: 'Brand turnaround tracking vs. Adidas share-of-voice' },
]

export async function loadPulseTerminalData() {
  const snapshotPath = path.join(process.cwd(), 'lib', 'data', 'pulse_snapshot.json')
  let snapshot: any = {
    generated_at: new Date().toISOString(),
    schedule_cron: '0 */6 * * *',
    assets: [],
    social_radar: [],
  }

  if (fs.existsSync(snapshotPath)) {
    try {
      snapshot = JSON.parse(fs.readFileSync(snapshotPath, 'utf-8'))
    } catch {
      // Fallback
    }
  }

  let user: any = null
  let runs: any[] = []
  let watchlistItems: Array<{ slug: string; notes: string }> = [...DEFAULT_WATCHLIST_ITEMS]
  let watchlistSlugs: string[] = DEFAULT_WATCHLIST_ITEMS.map((i) => i.slug)

  try {
    const supabase = await createClient()
    const { data: authData } = await supabase.auth.getUser()
    user = authData?.user || null

    const { data: runRows } = await supabase
      .from('scheduled_ingestion_runs')
      .select('*')
      .order('completed_at', { ascending: false })
      .limit(15)

    if (runRows && runRows.length > 0) {
      runs = runRows
    }

    if (user) {
      const { data: wlRows } = await supabase
        .from('user_watchlists')
        .select('id, notes, created_at, topic:topics(slug)')
        .eq('user_id', user.id)
        .order('created_at', { ascending: true })

      if (wlRows) {
        watchlistItems = wlRows
          .map((r: any) => ({
            slug: r.topic?.slug,
            notes: r.notes || 'Monitoring daily sentiment vs. price action',
          }))
          .filter((r: any) => Boolean(r.slug))
        watchlistSlugs = watchlistItems.map((i) => i.slug)
      }
    }
  } catch {
    // Graceful fallback if offline
  }

  return {
    snapshot,
    runs,
    watchlistSlugs,
    watchlistItems,
    user,
  }
}
