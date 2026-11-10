import { useState, useEffect, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Lock, Mail, User, Sparkles, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export function AuthPage() {
  const { user, signInWithEmail, signUpWithEmail } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const redirectTo = searchParams.get('redirect') || '/projects'

  const [mode, setMode] = useState<'signin' | 'signup'>(
    searchParams.get('mode') === 'signup' ? 'signup' : 'signin'
  )
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [infoMessage, setInfoMessage] = useState<string | null>(null)

  useEffect(() => {
    if (user) {
      navigate(redirectTo, { replace: true })
    }
  }, [user, navigate, redirectTo])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfoMessage(null)
    setSubmitting(true)

    try {
      if (mode === 'signin') {
        const { error: signInErr } = await signInWithEmail(email.trim(), password)
        if (signInErr) {
          setError(signInErr)
        } else {
          navigate(redirectTo, { replace: true })
        }
      } else {
        const { error: signUpErr, needsEmailConfirmation } = await signUpWithEmail(
          email.trim(),
          password,
          displayName
        )
        if (signUpErr) {
          setError(signUpErr)
        } else if (needsEmailConfirmation) {
          setInfoMessage(
            'Account created! Please check your email inbox to confirm your address before signing in.'
          )
          setMode('signin')
        } else {
          navigate(redirectTo, { replace: true })
        }
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-[#0b0c10] text-[#fffdf9] flex flex-col justify-between px-6 py-8">
      {/* Subtle Tokyo Night / Dusk ambient background radial */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: `
            radial-gradient(55% 50% at 50% 15%, rgba(122, 162, 247, 0.12) 0%, rgba(203, 166, 247, 0.06) 45%, rgba(11, 12, 16, 0) 100%),
            radial-gradient(40% 45% at 80% 85%, rgba(255, 184, 108, 0.08) 0%, rgba(11, 12, 16, 0) 100%)
          `,
        }}
      />

      {/* Top Bar */}
      <header className="relative z-10 mx-auto flex w-full max-w-[1200px] items-center justify-between">
        <Link
          to="/"
          className="inline-flex items-center gap-2.5 text-white/90 hover:text-white transition-colors"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-6 w-6 text-[#ffb86c]">
            <path d="M12 1.5C12.7 7.1 16.9 11.3 22.5 12C16.9 12.7 12.7 16.9 12 22.5C11.3 16.9 7.1 12.7 1.5 12C7.1 11.3 11.3 7.1 12 1.5Z" />
          </svg>
          <span className="font-sans text-[19px] font-semibold tracking-[-0.015em]">
            Nudge
          </span>
        </Link>

        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-white/65 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Home</span>
        </Link>
      </header>

      {/* Center Auth Card */}
      <main className="relative z-10 my-auto mx-auto w-full max-w-[430px]">
        <div className="rounded-2xl border border-white/[0.08] bg-[#12131c]/90 p-8 shadow-[0_24px_80px_rgba(0,0,0,0.65)] backdrop-blur-xl">
          <div className="mb-6 text-center">
            <div className="mx-auto mb-3 inline-flex items-center gap-1.5 rounded-full border border-[#ffb86c]/25 bg-[#ffb86c]/10 px-3 py-1 text-xs font-medium text-[#ffb86c]">
              <Sparkles className="h-3.5 w-3.5" />
              <span>AI-Guided Engineering Workspace</span>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-white">
              {mode === 'signin' ? 'Welcome back to Nudge' : 'Create your Nudge account'}
            </h1>
            <p className="mt-1.5 text-sm text-white/55">
              {mode === 'signin'
                ? 'Sign in to access your saved workspaces and AI mentor.'
                : 'Start debugging and hardening real-world systems.'}
            </p>
          </div>

          {/* Mode Toggle Pills */}
          <div className="mb-6 grid grid-cols-2 rounded-xl bg-[#0b0c10] p-1 border border-white/[0.06]">
            <button
              type="button"
              onClick={() => {
                setMode('signin')
                setError(null)
              }}
              className={`rounded-lg py-2 text-xs font-semibold transition-all cursor-pointer ${
                mode === 'signin'
                  ? 'bg-[#1f2335] text-white shadow-sm'
                  : 'text-white/50 hover:text-white/80'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('signup')
                setError(null)
              }}
              className={`rounded-lg py-2 text-xs font-semibold transition-all cursor-pointer ${
                mode === 'signup'
                  ? 'bg-[#1f2335] text-white shadow-sm'
                  : 'text-white/50 hover:text-white/80'
              }`}
            >
              Create Account
            </button>
          </div>

          {error && (
            <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-[#f38ba8]/30 bg-[#f38ba8]/10 px-3.5 py-3 text-xs text-[#f38ba8]">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {infoMessage && (
            <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-[#a6e3a1]/30 bg-[#a6e3a1]/10 px-3.5 py-3 text-xs text-[#a6e3a1]">
              <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{infoMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'signup' && (
              <div>
                <label className="mb-1.5 block text-xs font-medium text-white/70">
                  Name / Handle
                </label>
                <div className="relative">
                  <User className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" />
                  <input
                    type="text"
                    placeholder="Ada Lovelace"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    className="w-full rounded-xl border border-white/[0.08] bg-[#0b0c10] py-2.5 pl-10 pr-4 text-sm text-white placeholder-white/30 focus:border-[#7aa2f7] focus:outline-none transition-colors"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="mb-1.5 block text-xs font-medium text-white/70">
                Email Address
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" />
                <input
                  type="email"
                  required
                  placeholder="you@domain.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-xl border border-white/[0.08] bg-[#0b0c10] py-2.5 pl-10 pr-4 text-sm text-white placeholder-white/30 focus:border-[#7aa2f7] focus:outline-none transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-white/70">
                Password
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" />
                <input
                  type="password"
                  required
                  minLength={6}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-xl border border-white/[0.08] bg-[#0b0c10] py-2.5 pl-10 pr-4 text-sm text-white placeholder-white/30 focus:border-[#7aa2f7] focus:outline-none transition-colors"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="mt-2 w-full rounded-xl bg-white py-2.5 text-sm font-semibold text-[#11121d] shadow-[0_4px_20px_rgba(255,255,255,0.12)] transition-all hover:bg-white/90 disabled:opacity-50 cursor-pointer"
            >
              {submitting
                ? mode === 'signin'
                  ? 'Signing in...'
                  : 'Creating account...'
                : mode === 'signin'
                  ? 'Sign In to Workspace'
                  : 'Create Account'}
            </button>
          </form>
        </div>
      </main>

      <footer className="relative z-10 text-center text-xs text-white/35">
        Secured with Supabase Auth &bull; Synced to PostgreSQL
      </footer>
    </div>
  )
}

export default AuthPage

