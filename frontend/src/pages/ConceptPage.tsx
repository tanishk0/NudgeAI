import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { BookOpen, CheckCircle2, Clock3, Code2, Loader2, Sparkles } from 'lucide-react'
import { apiFetch } from '../lib/supabase'
import type { ProjectDetail } from '../types/workspace'
import '../styles/workbench.css'
import '../styles/concepts.css'

export default function ConceptPage() {
  const { projectId } = useParams()
  return <ConceptLesson key={projectId} />
}

function ConceptLesson() {
  const { projectId, taskId } = useParams()
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    apiFetch<ProjectDetail>(`/api/projects/${encodeURIComponent(projectId || '')}`, { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setProject(data) })
      .catch((e) => { if (!controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [projectId])

  useEffect(() => { window.scrollTo(0, 0) }, [taskId])

  const task = project?.tasks.find((item) => item.id === taskId)
  const available = project?.tasks.filter((item) => item.concept_markdown) || []
  const position = available.findIndex((item) => item.id === taskId)
  const previous = available[position - 1]
  const next = available[position + 1]
  const lessonUrl = (id: string) => `/projects/${projectId}/tasks/${id}/learn`

  if (error || (project && (!task || !task.concept_markdown))) return (
    <main className="brief-loading" role="alert">
      <p>{error || 'This concept lesson could not be found.'}</p>
      <Link to={`/projects/${projectId}`}>Back to project</Link>
    </main>
  )
  if (!project || !task) return <main className="brief-loading"><Loader2 className="spin" /> Loading concept lesson…</main>

  const readingMinutes = Math.max(1, Math.ceil((task.concept_markdown || '').split(/\s+/).length / 180))
  return (
    <div className="project-brief concept-page">
      <nav className="brief-nav" aria-label="Lesson navigation">
        <Link to="/" className="nudge-wordmark"><Sparkles size={21} /> nudge<span> / academy</span></Link>
        <Link to={`/projects/${project.id}`}>Project brief</Link>
        <Link to={`/workspace/${project.id}`}><Code2 size={17} /> Return to workspace</Link>
      </nav>
      <main className="concept-layout">
        <aside className="concept-sidebar">
          <Link to={`/projects/${project.id}`}>{project.title}</Link>
          <h2>Concept library</h2>
          <p>Read any lesson at your own pace. Coding tasks unlock as you build.</p>
          <nav aria-label="Concept lessons">
            {available.map((item) => <Link key={item.id} to={lessonUrl(item.id)} aria-current={item.id === task.id ? 'page' : undefined}>
              <span>{item.order}</span><span>{item.title}</span>
            </Link>)}
          </nav>
        </aside>
        <article className="concept-article">
          <header>
            <div className="brief-eyebrow"><span className="outline-pill"><BookOpen size={14} /> LEARN THE CONCEPT</span></div>
            <p className="concept-kicker">Task {task.order} of {project.tasks.length}</p>
            <h1>{task.title}</h1>
            <p className="concept-intro">{task.objective}</p>
            <div className="brief-meta"><span><Clock3 size={16} /> {readingMinutes} min read</span>{task.estimated_time && <span>Build estimate: {task.estimated_time}</span>}</div>
          </header>
          <div className="concept-content"><ReactMarkdown remarkPlugins={[remarkGfm]}>{task.concept_markdown}</ReactMarkdown></div>
          <section className="concept-practice">
            <CheckCircle2 size={24} />
            <div><h2>Put the concept into practice</h2><p>Implement this task in <code>{task.target_file}</code>, then use Check task for feedback.</p>
              <Link className="primary-button" to={`/workspace/${project.id}`}>Return to workspace</Link>
            </div>
          </section>
          <footer className="concept-pagination">
            {previous ? <Link to={lessonUrl(previous.id)}><small>Previous concept</small>{previous.title}</Link> : <span />}
            {next && <Link to={lessonUrl(next.id)}><small>Next concept</small>{next.title}</Link>}
          </footer>
        </article>
      </main>
    </div>
  )
}
