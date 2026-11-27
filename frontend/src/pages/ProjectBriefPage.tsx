import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  BookOpen,
  Check,
  CheckCircle2,
  ChevronLeft,
  Clock3,
  Code2,
  Files,
  GraduationCap,
  Layers3,
  Loader2,
  ShieldCheck,
  Sparkles,
  Terminal,
} from 'lucide-react'
import { apiFetch } from '../lib/supabase'
import { useAuth } from '../context/AuthContext'
import type { ProjectDetail } from '../types/workspace'
import '../styles/workbench.css'
import '../styles/concepts.css'

export default function ProjectBriefPage() {
  const { projectId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    apiFetch<ProjectDetail>(`/api/projects/${projectId}`, {
      signal: controller.signal,
    })
      .then(setProject)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message)
      })
    return () => controller.abort()
  }, [projectId])
  if (!project)
    return (
      <div className="brief-loading">
        {error ? (
          <>
            <p>{error}</p>
            <Link to="/projects">Back to projects</Link>
          </>
        ) : (
          <>
            <Loader2 className="spin" /> Preparing your project brief
          </>
        )}
      </div>
    )
  const start = () =>
    navigate(
      user
        ? `/workspace/${project.id}`
        : `/auth?redirect=${encodeURIComponent(`/workspace/${project.id}`)}`,
    )
  return (
    <div className="project-brief">
      <nav className="brief-nav">
        <Link to="/" className="nudge-wordmark">
          <Sparkles size={21} /> nudge<span> / academy</span>
        </Link>
        <Link to="/projects">
          <ChevronLeft size={16} /> All projects
        </Link>
      </nav>
      <main className="brief-container">
        <div className="brief-eyebrow">
          <span className="outline-pill">
            <BookOpen size={14} /> PROJECT BRIEF
          </span>
          <span>Read the brief. Make a plan. Build with confidence.</span>
        </div>
        <div className="brief-grid">
          <div className="brief-main">
            <div className="brief-category">{project.category}</div>
            <h1>{project.title}</h1>
            <p className="brief-subtitle">{project.subtitle}</p>
            <div className="brief-meta">
              <span
                className={`difficulty ${project.difficulty.toLowerCase()}`}
              >
                <Layers3 size={15} /> {project.difficulty}
              </span>
              <span>
                <Clock3 size={16} /> About {project.estimated_minutes} minutes
              </span>
              <span>
                <CheckCircle2 size={16} /> {project.tasks.length} guided tasks
              </span>
            </div>
            <section className="brief-section">
              <div className="section-heading">
                <Code2 size={20} />
                <h2>What you’ll build</h2>
              </div>
              <p>{project.deliverable || project.system_context}</p>
              <div className="brief-context">
                <span>THE SCENARIO</span>
                <p>{project.problem_statement}</p>
              </div>
            </section>
            <section className="brief-section prerequisites">
              <div className="section-heading">
                <BookOpen size={20} />
                <h2>Prerequisites</h2>
              </div>
              <p>Before you start, you should be comfortable with:</p>
              <ul>
                {project.prerequisites.map((item) => (
                  <li key={item}>
                    <Check size={16} />
                    {item}
                  </li>
                ))}
              </ul>
            </section>
            <section className="brief-section">
              <div className="section-heading">
                <GraduationCap size={21} />
                <h2>What you’ll learn</h2>
              </div>
              <div className="outcomes-grid">
                {project.learning_outcomes.map((outcome) => (
                  <div key={outcome}>
                    <span className="check-icon">
                      <Check size={15} />
                    </span>
                    <p>{outcome}</p>
                  </div>
                ))}
              </div>
            </section>
            <section className="brief-section">
              <div className="section-heading">
                <Terminal size={20} />
                <h2>Your toolkit</h2>
              </div>
              <p>
                Work with these technologies in a ready-to-edit project
                workspace.
              </p>
              <div className="technology-list">
                {project.technologies.map((tech) => (
                  <span key={tech}>
                    <Code2 size={14} />
                    {tech}
                  </span>
                ))}
              </div>
            </section>
            <section className="brief-section">
              <div className="section-heading">
                <Layers3 size={20} />
                <h2>The build plan</h2>
              </div>
              <p>
                One focused task at a time, with clear acceptance criteria and a
                mentor when you need one.
              </p>
              <ol className="brief-roadmap">
                {project.tasks.map((task) => (
                  <li key={task.id}>
                    <div className="roadmap-index">{task.order}</div>
                    <div>
                      <h3>{task.title}</h3>
                      {task.estimated_time && <small className="phase-roadmap-meta">{task.estimated_time}</small>}
                      <p>{task.objective}</p>
                      <span>
                        {task.validation_criteria.length} acceptance checks ·{' '}
                        {task.target_file}
                      </span>
                      {task.concept_markdown && <Link className="learn-concept-link" to={`/projects/${project.id}/tasks/${task.id}/learn`}><BookOpen size={16} /> Learn the concept</Link>}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          </div>
          <aside className="brief-aside">
            <div className="launch-card">
              <div className="launch-art">
                <div className="launch-window">
                  <div>
                    <i />
                    <i />
                    <i />
                    <span>your next project</span>
                  </div>
                  <pre>
                    <span>def</span> build_something():{'\n'} learn_by_doing()
                    {'\n'} <span>return</span> confidence
                  </pre>
                  <div className="launch-ready">
                    <CheckCircle2 size={14} /> Your workspace is ready
                  </div>
                </div>
              </div>
              <div className="launch-card-content">
                <h2>
                  Make it work.
                  <br />
                  <span>Understand why.</span>
                </h2>
                <p>
                  Your own editor, a task roadmap, and an AI mentor that works
                  with your code.
                </p>
                <button className="primary-button" onClick={start}>
                  <Terminal size={17} />
                  {user ? 'Start building' : 'Sign in & start building'}
                </button>
                <p className="launch-note">
                  Your progress is saved to your account.
                </p>
                <div className="launch-features">
                  <span>
                    <Files size={16} /> Real project files
                  </span>
                  <span>
                    <ShieldCheck size={16} /> Clear acceptance checks
                  </span>
                  <span>
                    <Sparkles size={16} /> Progressive hints, at your pace
                  </span>
                </div>
              </div>
            </div>
          </aside>
        </div>
        <footer className="brief-footer">
          <Sparkles size={16} />
          <span>Less copy-paste. More “I understand this.”</span>
          <Link to="/projects">Explore other projects</Link>
        </footer>
      </main>
    </div>
  )
}
