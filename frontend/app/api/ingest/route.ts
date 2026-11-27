import { NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'
import fs from 'fs'
import { createClient } from '@/lib/supabase/server'

const TEN_MINUTES_MS = 4 * 60 * 1000

function getPidFilePath() {
  return path.resolve(process.cwd(), '..', 'output', 'ingest_pid.json')
}

function isLocalProcessRunning(): { running: boolean; startedAt?: number; topic?: string } {
  const pidPath = getPidFilePath()
  if (!fs.existsSync(pidPath)) return { running: false }
  try {
    const info = JSON.parse(fs.readFileSync(pidPath, 'utf-8'))
    const pid = Number(info?.pid)
    const startedAt = Number(info?.startedAt || 0)
    if (!pid || Date.now() - startedAt > TEN_MINUTES_MS) {
      fs.unlinkSync(pidPath)
      return { running: false }
    }
    // Signal 0 checks if the OS process is still alive without killing it
    process.kill(pid, 0)
    return { running: true, startedAt, topic: info?.topic }
  } catch {
    try {
      fs.unlinkSync(pidPath)
    } catch {
      // Ignore
    }
    return { running: false }
  }
}

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
    (r: any) => r.status === 'completed' && Number(r.topics_processed || 0) > 0
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

    const dbState = detectActiveRun(runs || [])
    const localState = isLocalProcessRunning()
    const isRunning = dbState.isRunning || localState.running

    return NextResponse.json({
      status: 'ok',
      isRunning,
      activeRun: dbState.activeRun || (localState.running ? localState : null),
      latestCompletedAt: dbState.latestCompletedAt || snapshot?.generated_at || null,
      snapshotGeneratedAt: snapshot?.generated_at || null,
      dbSynced: dbState.latestCompletedAt ? true : snapshot?.db_synced ?? null,
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
    const isAll = !topic || topic.toUpperCase() === 'ALL'
    const mode: 'prices_only' | 'full' =
      body?.mode === 'full' || body?.mode === 'prices_only'
        ? body.mode
        : isAll
        ? 'prices_only'
        : 'full'

    const localState = isLocalProcessRunning()
    if (localState.running) {
      return NextResponse.json(
        {
          status: 'already_running',
          isRunning: true,
          activeRun: localState,
          topic: topic || 'ALL (14 Topics)',
          message: 'A live data refresh is already in progress.',
        },
        { status: 202 }
      )
    }

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
      const response = await fetch(new URL('/ingest', agentServiceUrl), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: topic || 'ALL',
          mode,
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

    // Local / VM deployment: launch detached background process & track its PID
    const projectRoot = path.resolve(process.cwd(), '..')
    const schedulerScript = path.join(projectRoot, 'agents', 'scheduler.py')
    const venvPython = path.join(projectRoot, '.venv', 'bin', 'python')
    const pythonBin = fs.existsSync(venvPython) ? venvPython : 'python3'

    const outputDir = path.join(projectRoot, 'output')
    fs.mkdirSync(outputDir, { recursive: true })
    const logFd = fs.openSync(path.join(outputDir, 'ingest_live.log'), 'a')

    const args = [schedulerScript, '--trigger', 'web_dashboard']
    if (topic && topic.toUpperCase() !== 'ALL') {
      args.push('--topic', topic)
    }
    if (mode === 'prices_only') {
      args.push('--prices-only')
    }

    const child = spawn(pythonBin, args, {
      cwd: projectRoot,
      detached: true,
      stdio: ['ignore', logFd, logFd],
    })
    child.unref()

    fs.writeFileSync(
      getPidFilePath(),
      JSON.stringify({ pid: child.pid, startedAt: Date.now(), topic: topic || 'ALL' }),
      'utf-8'
    )

    return NextResponse.json(
      {
        status: 'started',
        isRunning: true,
        topic: topic || 'ALL (14 Topics)',
        message: 'Background multi-agent refresh started.',
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
