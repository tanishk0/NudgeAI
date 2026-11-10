import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import type { Session, User } from '@supabase/supabase-js'
import { apiFetch, supabase } from '../lib/supabase'

export interface BackendUserProfile {
  id: string
  email: string
  display_name: string | null
  avatar_url: string | null
}

interface AuthContextValue {
  session: Session | null
  user: User | null
  profile: BackendUserProfile | null
  loading: boolean
  signInWithEmail: (email: string, password: string) => Promise<{ error: string | null }>
  signUpWithEmail: (
    email: string,
    password: string,
    displayName: string
  ) => Promise<{ error: string | null; needsEmailConfirmation: boolean }>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<BackendUserProfile | null>(null)
  const [loading, setLoading] = useState(true)

  const syncUserWithBackend = async (activeSession: Session | null) => {
    if (!activeSession?.access_token) {
      setProfile(null)
      return
    }
    try {
      const me = await apiFetch<BackendUserProfile>('/api/auth/me')
      setProfile(me)
    } catch (err) {
      console.warn('[Nudge Auth] Backend profile sync warning:', err)
    }
  }

  useEffect(() => {
    let mounted = true

    supabase.auth.getSession().then(({ data: { session: initialSession } }) => {
      if (!mounted) return
      setSession(initialSession)
      setUser(initialSession?.user ?? null)
      setLoading(false)
      void syncUserWithBackend(initialSession)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
      setUser(nextSession?.user ?? null)
      setLoading(false)
      void syncUserWithBackend(nextSession)
    })

    return () => {
      mounted = false
      subscription.unsubscribe()
    }
  }, [])

  const signInWithEmail = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })
    return { error: error ? error.message : null }
  }

  const signUpWithEmail = async (
    email: string,
    password: string,
    displayName: string
  ) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: displayName.trim() || email.split('@')[0],
        },
      },
    })
    if (error) {
      return { error: error.message, needsEmailConfirmation: false }
    }
    const needsEmailConfirmation = Boolean(data.user && !data.session)
    return { error: null, needsEmailConfirmation }
  }

  const signOut = async () => {
    await supabase.auth.signOut()
    setProfile(null)
  }

  return (
    <AuthContext.Provider
      value={{
        session,
        user,
        profile,
        loading,
        signInWithEmail,
        signUpWithEmail,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}

