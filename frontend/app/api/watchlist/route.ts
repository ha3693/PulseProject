import { NextResponse } from 'next/server'
import { revalidatePath } from 'next/cache'
import { createClient } from '@/lib/supabase/server'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const supabase = await createClient()
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json(
        { authenticated: false, items: [] },
        { headers: { 'Cache-Control': 'no-store, max-age=0' } }
      )
    }

    const { data, error } = await supabase
      .from('user_watchlists')
      .select(`
        id,
        notes,
        created_at,
        topic:topics (
          id,
          slug,
          name,
          ticker,
          category
        )
      `)
      .eq('user_id', user.id)
      .order('created_at', { ascending: true })

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 400 })
    }

    return NextResponse.json(
      { authenticated: true, items: data || [] },
      { headers: { 'Cache-Control': 'no-store, max-age=0' } }
    )
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || 'Server error' }, { status: 500 })
  }
}

export async function POST(request: Request) {
  try {
    const supabase = await createClient()
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 })
    }

    const { slug, notes } = await request.json()
    if (!slug) {
      return NextResponse.json({ error: 'Topic slug required' }, { status: 400 })
    }

    const { data: topicRow } = await supabase
      .from('topics')
      .select('id, slug, name, ticker')
      .eq('slug', slug)
      .single()

    if (!topicRow) {
      return NextResponse.json({ error: 'Topic not found' }, { status: 404 })
    }

    const { data, error } = await supabase
      .from('user_watchlists')
      .upsert(
        {
          user_id: user.id,
          topic_id: topicRow.id,
          notes: notes ?? 'Monitoring sentiment vs. price divergence',
        },
        { onConflict: 'user_id,topic_id' }
      )
      .select()
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 400 })
    }

    // Invalidate Next.js Server Component cache across all routes
    revalidatePath('/', 'layout')
    revalidatePath('/watchlist')
    revalidatePath('/dashboard')
    revalidatePath('/terminal')

    return NextResponse.json({ status: 'added', item: data })
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || 'Server error' }, { status: 500 })
  }
}

export async function DELETE(request: Request) {
  try {
    const supabase = await createClient()
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 })
    }

    const { searchParams } = new URL(request.url)
    const slug = searchParams.get('slug')
    if (!slug) {
      return NextResponse.json({ error: 'Topic slug required' }, { status: 400 })
    }

    const { data: topicRow } = await supabase
      .from('topics')
      .select('id')
      .eq('slug', slug)
      .single()

    if (!topicRow) {
      return NextResponse.json({ error: 'Topic not found' }, { status: 404 })
    }

    const { error } = await supabase
      .from('user_watchlists')
      .delete()
      .eq('user_id', user.id)
      .eq('topic_id', topicRow.id)

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 400 })
    }

    // Invalidate Next.js Server Component cache across all routes
    revalidatePath('/', 'layout')
    revalidatePath('/watchlist')
    revalidatePath('/dashboard')
    revalidatePath('/terminal')

    return NextResponse.json({ status: 'removed', slug })
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || 'Server error' }, { status: 500 })
  }
}
