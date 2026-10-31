import { redirect } from 'next/navigation'
import WatchlistView from '@/components/WatchlistView'
import { loadPulseTerminalData } from '@/lib/data/loadPulseData'

export const dynamic = 'force-dynamic'

export default async function WatchlistPage() {
  const { snapshot, watchlistSlugs, user } = await loadPulseTerminalData()

  if (!user) {
    redirect('/login?redirectTo=/watchlist')
  }

  return (
    <WatchlistView
      userEmail={user.email || ''}
      assets={snapshot?.assets || []}
      initialWatchlistSlugs={watchlistSlugs}
    />
  )
}
