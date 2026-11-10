import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Clock,
  Layers,
  ShieldAlert,
  ArrowRight,
  LogOut,
  Terminal,
  Sparkles,
} from 'lucide-react'
import { apiFetch } from '../lib/supabase'
import { useAuth } from '../context/AuthContext'

export interface ProjectSummary {
  id: string
  title: string
  subtitle: string
  difficulty: 'Beginner' | 'Intermediate' | 'Advanced'
  category: string
  tags: string[]
  estimated_minutes: number
  ai_failure_mode: string
  task_count: number
}

export function ProjectsHub() {
  const { user, profile, signOut } = useAuth()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('All')

  useEffect(() => {
    let active = true
    apiFetch<ProjectSummary[]>('/api/projects')
      .then((data) => {
        if (active) {
          setProjects(data)
          setError(null)
        }
      })
      .catch((err: Error) => {
        if (active) {
          setError(err.message || 'Failed to load projects from backend.')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const filteredProjects =
    filter === 'All'
      ? projects
      : projects.filter((p) => p.difficulty === filter)

  const difficultyStyles: Record<ProjectSummary['difficulty'], string> = {
    Beginner: 'border-[#a6e3a1]/30 bg-[#a6e3a1]/10 text-[#a6e3a1]',
    Intermediate: 'border-[#f9e2af]/30 bg-[#f9e2af]/10 text-[#f9e2af]',
    Advanced: 'border-[#f38ba8]/30 bg-[#f38ba8]/10 text-[#f38ba8]',
  }

  const handleLaunchProject = (projectId: string) => {
    if (!user) {
      navigate(`/auth?redirect=${encodeURIComponent(`/workspace/${projectId}`)}`)
      return
    }
    navigate(`/workspace/${projectId}`)
  }

  return (
    <div className="min-h-screen w-full bg-[#0b0c10] text-[#fffdf9]">
      {/* Top IDE-style Header */}
      <header className="sticky top-0 z-20 border-b border-white/[0.07] bg-[#0b0c10]/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between px-6 py-4">
          <Link to="/" className="inline-flex items-center gap-2.5 text-white group">
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              className="h-5 w-5 text-[#ffb86c] transition-transform duration-300 group-hover:scale-110"
            >
              <path d="M12 1.5C12.7 7.1 16.9 11.3 22.5 12C16.9 12.7 12.7 16.9 12 22.5C11.3 16.9 7.1 12.7 1.5 12C7.1 11.3 11.3 7.1 12 1.5Z" />
            </svg>
            <span className="font-sans text-[18px] font-semibold tracking-[-0.015em]">
              Nudge
            </span>
            <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 font-mono text-[11px] text-white/55">
              PROJECTS
            </span>
          </Link>

          <div className="flex items-center gap-4">
            {user ? (
              <>
                <div className="flex items-center gap-2.5 rounded-full border border-white/[0.08] bg-[#141622] px-3.5 py-1.5 text-xs">
                  <span className="h-2 w-2 rounded-full bg-[#a6e3a1]" />
                  <span className="font-medium text-white/90">
                    {profile?.display_name || user.email}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => void signOut()}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs text-white/70 hover:bg-white/[0.08] hover:text-white transition-colors cursor-pointer"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  <span>Sign Out</span>
                </button>
              </>
            ) : (
              <Link
                to="/auth"
                className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-1.5 text-xs font-semibold text-[#11121d] hover:bg-white/90 transition-colors"
              >
                <span>Sign In</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-[1320px] px-6 py-12">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div>
            <div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-[#7aa2f7]/25 bg-[#7aa2f7]/10 px-3 py-1 text-xs font-medium text-[#7aa2f7]">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Real-World AI Failure Modes</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-white">
              Engineering Challenges
            </h1>
            <p className="mt-2 max-w-[640px] text-sm sm:text-base text-white/60">
              Select a brittle system generated by an LLM, inspect the vulnerability in the Monaco IDE, and harden it with progressive Socratic nudges.
            </p>
          </div>

          {/* Difficulty Filter */}
          <div className="flex items-center gap-1.5 rounded-xl border border-white/[0.07] bg-[#12131c] p-1 self-start">
            {['All', 'Beginner', 'Intermediate', 'Advanced'].map((level) => (
              <button
                key={level}
                type="button"
                onClick={() => setFilter(level)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                  filter === level
                    ? 'bg-[#1f2335] text-white'
                    : 'text-white/50 hover:text-white/80'
                }`}
              >
                {level}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className="h-[340px] animate-pulse rounded-2xl border border-white/[0.06] bg-[#12131c]"
              />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-[#f38ba8]/30 bg-[#f38ba8]/10 p-6 text-sm text-[#f38ba8]">
            <p className="font-semibold">Could not load projects from FastAPI backend</p>
            <p className="mt-1 text-white/70">{error}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {filteredProjects.map((project) => (
              <div
                key={project.id}
                className="group flex flex-col justify-between rounded-2xl border border-white/[0.08] bg-[#12131c]/90 p-6 transition-all hover:border-[#7aa2f7]/40 hover:bg-[#151722] shadow-[0_12px_40px_rgba(0,0,0,0.4)]"
              >
                <div>
                  {/* Top Badges */}
                  <div className="flex items-center justify-between gap-2 mb-4">
                    <span
                      className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-[11px] font-semibold ${
                        difficultyStyles[project.difficulty]
                      }`}
                    >
                      {project.difficulty}
                    </span>
                    <span className="text-xs text-white/45 font-mono">
                      {project.category}
                    </span>
                  </div>

                  {/* Title & Subtitle */}
                  <h2 className="text-lg font-semibold text-white group-hover:text-[#7aa2f7] transition-colors">
                    {project.title}
                  </h2>
                  <p className="mt-2 text-xs leading-relaxed text-white/60">
                    {project.subtitle}
                  </p>

                  {/* AI Failure Mode Callout */}
                  <div className="mt-4 rounded-xl border border-[#ffb86c]/20 bg-[#ffb86c]/[0.05] p-3">
                    <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#ffb86c]">
                      <ShieldAlert className="h-3.5 w-3.5" />
                      <span>Why the AI Failed</span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-white/70 line-clamp-3">
                      {project.ai_failure_mode}
                    </p>
                  </div>

                  {/* Tags */}
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {project.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-md bg-white/[0.04] border border-white/[0.06] px-2 py-0.5 font-mono text-[11px] text-white/60"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Footer Meta & CTA */}
                <div className="mt-6 pt-4 border-t border-white/[0.06] flex items-center justify-between">
                  <div className="flex items-center gap-4 text-xs text-white/50">
                    <span className="inline-flex items-center gap-1">
                      <Layers className="h-3.5 w-3.5 text-[#cba6f7]" />
                      {project.task_count} tasks
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5 text-[#7aa2f7]" />
                      {project.estimated_minutes}m
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleLaunchProject(project.id)}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3.5 py-2 text-xs font-semibold text-[#11121d] transition-all hover:bg-[#7aa2f7] hover:text-[#0b0c10] cursor-pointer"
                  >
                    <Terminal className="h-3.5 w-3.5" />
                    <span>Open IDE</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

export default ProjectsHub
