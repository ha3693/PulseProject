import { NextResponse } from 'next/server'
import { execFile } from 'child_process'
import { promisify } from 'util'
import path from 'path'
import fs from 'fs'
import { createClient } from '@/lib/supabase/server'

const execFileAsync = promisify(execFile)

export async function GET() {
  try {
    const supabase = await createClient()
    const { data: runs } = await supabase
      .from('scheduled_ingestion_runs')
      .select('*')
      .order('completed_at', { ascending: false })
      .limit(15)

    const snapshotPath = path.join(process.cwd(), 'lib', 'data', 'pulse_snapshot.json')
    let snapshot = null
    if (fs.existsSync(snapshotPath)) {
      snapshot = JSON.parse(fs.readFileSync(snapshotPath, 'utf-8'))
    }

    return NextResponse.json({
      status: 'ok',
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

    const projectRoot = path.resolve(process.cwd(), '..')
    const schedulerScript = path.join(projectRoot, 'agents', 'scheduler.py')

    const args = [schedulerScript, '--trigger', 'web_dashboard']
    if (topic && topic !== 'ALL') {
      args.push('--topic', topic)
    }

    await execFileAsync('python3', args, {
      cwd: projectRoot,
      timeout: 60000,
    })

    const snapshotPath = path.join(process.cwd(), 'lib', 'data', 'pulse_snapshot.json')
    const snapshot = fs.existsSync(snapshotPath)
      ? JSON.parse(fs.readFileSync(snapshotPath, 'utf-8'))
      : null

    const supabase = await createClient()
    const { data: runs } = await supabase
      .from('scheduled_ingestion_runs')
      .select('*')
      .order('completed_at', { ascending: false })
      .limit(15)

    return NextResponse.json({
      status: 'completed',
      topic: topic || 'ALL (14 Topics)',
      runs: runs || [],
      snapshot,
    })
  } catch (err: any) {
    return NextResponse.json(
      { status: 'error', message: err?.message || 'Agent ingestion failed' },
      { status: 500 }
    )
  }
}

