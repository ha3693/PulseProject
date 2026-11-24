import { NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'
import fs from 'fs'
import { createClient } from '@/lib/supabase/server'

const TEN_MINUTES_MS = 10 * 60 * 1000

function detectActiveRun(runs: any[]): { isRunning: boolean; activeRun: any | null; latestCompletedAt: string | null } {
  const realRuns = (runs || []).filter(
    (r: any) => !Array.isArray(r?.agents_invoked) || !r.agents_invoked.includes('pg_cron_rollup')
  )
  const latestReal = realRuns[0] || null
  const isRunning = Boolean(
    latestReal &&
      latestReal.status === 'running' &&
      Date.now() - new Date(latestReal.started_at || latestReal.completed_at).getTime() < TEN_MINUTES_MS
  )
  const latestCompleted = realRuns.find(
    (r: any) => r.status === 'completed' && Number(r.posts_ingested || 0) > 0
  )
  return {
    isRunning,
    activeRun: isRunning ? latestReal : null,
    latestCompletedAt: latestCompleted?.completed_at || null,
  }
}

export async function GET() {
  try {
    const supabase = await createClient()
    const { data: runs } = await supabase
      .from('scheduled_ingestion_runs')
      .select('*')
      .order('started_at', { ascending: false })
      .limit(15)

    const snapshotPath = path.join(process.cwd(), 'lib', 'data', 'pulse_snapshot.json')
    let snapshot = null
    if (fs.existsSync(snapshotPath)) {
      snapshot = JSON.parse(fs.readFileSync(snapshotPath, 'utf-8'))
    }

    const { isRunning, activeRun, latestCompletedAt } = detectActiveRun(runs || [])

    return NextResponse.json({
      status: 'ok',
      isRunning,
      activeRun,
      latestCompletedAt: latestCompletedAt || snapshot?.generated_at || null,
      runs: runs || [],
      snapshot,
    })
  } catch (err: any) {
    return NextResponse.json(
      { status: 'error', message: err?.message || 'Failed to load ingestion state' },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}))
    const topic = body?.topic ? String(body.topic).trim() : null

    const supabase = await createClient()
    const { data: existingRuns } = await supabase
      .from('scheduled_ingestion_runs')
      .select('*')
      .order('started_at', { ascending: false })
      .limit(10)

    const { isRunning, activeRun } = detectActiveRun(existingRuns || [])
    if (isRunning) {
      return NextResponse.json(
        {
          status: 'already_running',
          isRunning: true,
          activeRun,
          topic: topic || 'ALL (14 Topics)',
          message: 'A live data refresh is already in progress.',
        },
        { status: 202 }
      )
    }

    const agentServiceUrl = process.env.AGENT_SERVICE_URL

    if (agentServiceUrl) {
      // Call the internal Python `app` service via the Vercel Service Binding URL
      const response = await fetch(new URL('/ingest', agentServiceUrl), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: topic || 'ALL',
          trigger: 'web_dashboard',
        }),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData?.message || `Agent service responded with ${response.status}`)
      }

      const result = await response.json()
      const { data: runs } = await supabase
        .from('scheduled_ingestion_runs')
        .select('*')
        .order('started_at', { ascending: false })
        .limit(15)

      return NextResponse.json({
        status: 'completed',
        isRunning: false,
        topic: topic || 'ALL (14 Topics)',
        runs: runs || [],
        snapshot: result?.snapshot || null,
      })
    }

    // Local / VM deployment: launch detached background process so navigating away does not abort it
    const projectRoot = path.resolve(process.cwd(), '..')
    const schedulerScript = path.join(projectRoot, 'agents', 'scheduler.py')
    const venvPython = path.join(projectRoot, '.venv', 'bin', 'python')
    const pythonBin = fs.existsSync(venvPython) ? venvPython : 'python3'

    const args = [schedulerScript, '--trigger', 'web_dashboard']
    if (topic && topic !== 'ALL') {
      args.push('--topic', topic)
    }

    const child = spawn(pythonBin, args, {
      cwd: projectRoot,
      detached: true,
      stdio: 'ignore',
    })
    child.unref()

    return NextResponse.json(
      {
        status: 'started',
        isRunning: true,
        topic: topic || 'ALL (14 Topics)',
        message: 'Background multi-agent refresh started and will sync to Supabase.',
      },
      { status: 202 }
    )
  } catch (err: any) {
    return NextResponse.json(
      { status: 'error', message: err?.message || 'Agent ingestion failed' },
      { status: 500 }
    )
  }
}
