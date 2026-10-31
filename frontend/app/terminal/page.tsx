import PulseTerminal from '@/components/PulseTerminal'
import { loadPulseTerminalData } from '@/lib/data/loadPulseData'

export const dynamic = 'force-dynamic'

export default async function TerminalPage({
  searchParams,
}: {
  searchParams?: { asset?: string; tab?: 'market' | 'brand' | 'backtest' | 'social' | 'pipeline' }
}) {
  const { snapshot, runs, watchlistSlugs, user } = await loadPulseTerminalData()

  const validTabs = ['market', 'brand', 'backtest', 'social', 'pipeline']
  const initialTab =
    searchParams?.tab && validTabs.includes(searchParams.tab) ? searchParams.tab : 'market'
  const initialAssetSlug = searchParams?.asset ? searchParams.asset.toLowerCase() : 'nvda'

  return (
    <div>
      <PulseTerminal
        initialSnapshot={snapshot}
        initialRuns={runs}
        initialWatchlistSlugs={watchlistSlugs}
        userEmail={user?.email || null}
        initialTab={initialTab}
        initialAssetSlug={initialAssetSlug}
      />
    </div>
  )
}

