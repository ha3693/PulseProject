import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

// Routes that require an active authenticated session
const PROTECTED_ROUTES = ['/dashboard', '/watchlist', '/account', '/settings']

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet: { name: string; value: string; options?: any }[]) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          )
          supabaseResponse = NextResponse.next({
            request,
          })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  const pathname = request.nextUrl.pathname
  const code = request.nextUrl.searchParams.get('code')

  // If Supabase email confirmation redirected to /?code=... instead of /auth/callback,
  // exchange the PKCE code right here and redirect into /dashboard with session cookies attached!
  if (code && !pathname.startsWith('/auth/callback')) {
    const { error } = await supabase.auth.exchangeCodeForSession(code)
    const redirectUrl = request.nextUrl.clone()
    redirectUrl.searchParams.delete('code')
    redirectUrl.pathname = error ? '/login' : '/dashboard'
    if (error) {
      redirectUrl.searchParams.set('error', error.message)
    }

    const redirectResponse = NextResponse.redirect(redirectUrl)
    supabaseResponse.cookies.getAll().forEach((c) => {
      redirectResponse.cookies.set(c.name, c.value)
    })
    return redirectResponse
  }

  // Validate the JWT against Supabase Auth
  const {
    data: { user },
  } = await supabase.auth.getUser()

  // 1. Redirect unauthenticated users trying to access protected routes
  const isProtectedRoute = PROTECTED_ROUTES.some((route) =>
    pathname.startsWith(route)
  )

  if (isProtectedRoute && !user) {
    const redirectUrl = request.nextUrl.clone()
    redirectUrl.pathname = '/login'
    redirectUrl.searchParams.set('redirectTo', pathname)
    return NextResponse.redirect(redirectUrl)
  }

  // 2. Redirect authenticated users away from /login to /dashboard
  if (user && pathname.startsWith('/login')) {
    const redirectUrl = request.nextUrl.clone()
    redirectUrl.pathname = '/dashboard'
    return NextResponse.redirect(redirectUrl)
  }

  return supabaseResponse
}
