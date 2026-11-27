import { createClient } from '@supabase/supabase-js'

const supabaseUrl =
  (import.meta.env.VITE_SUPABASE_URL as string | undefined)?.trim() || ''
const supabaseAnonKey = (
  (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) ||
  (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined) ||
  ''
).trim()

export const API_BASE_URL = (
  (import.meta.env.DEV && import.meta.env.VITE_DEMO_MODE === 'true'
    ? 'http://localhost:8001'
    : (import.meta.env.VITE_API_BASE_URL as string | undefined)) ||
  'http://localhost:8000'
)
  .trim()
  .replace(/\/$/, '')

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
})

export async function apiRequest(
  endpoint: string,
  options: RequestInit = {},
): Promise<Response> {
  const {
    data: { session },
  } = await supabase.auth.getSession()

  const headers = new Headers(options.headers || {})
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json')
  }
  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`)
  }

  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    let errMsg = `Request failed (${res.status})`
    try {
      const errBody = await res.json()
      if (errBody?.detail) {
        errMsg =
          typeof errBody.detail === 'string'
            ? errBody.detail
            : JSON.stringify(errBody.detail)
      }
    } catch {
      // ignore JSON parse errors
    }
    throw new ApiError(errMsg, res.status)
  }

  return res
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  return (await apiRequest(endpoint, options)).json() as Promise<T>
}
