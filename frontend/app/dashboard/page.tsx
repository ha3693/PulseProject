import { redirect } from 'next/navigation'
import PersonalDashboard from '@/components/PersonalDashboard'
import { loadPulseTerminalData } from '@/lib/data/loadPulseData'
import { createClient } from '@/lib/supabase/server'

export const dynamic = 'force-dynamic'

export default async function DashboardPage() {
  const { snapshot, runs, watchlistItems, user } = await loadPulseTerminalData()

  if (!user) {
    redirect('/login?redirectTo=/dashboard')
  }

  let fullName: string | null = null

  try {
    const supabase = await createClient()
    const { data: profile } = await supabase
      .from('profiles')
      .select('full_name')
      .eq('id', user.id)
      .single()

    fullName = profile?.full_name || user.user_metadata?.full_name || null
  } catch {
    // Fallback
  }

  return (
    <PersonalDashboard
      userEmail={user.email || ''}
      userId={user.id}
      fullName={fullName}
      assets={snapshot?.assets || []}
      initialWatchlist={watchlistItems}
      recentRuns={runs}
    />
  )
}
