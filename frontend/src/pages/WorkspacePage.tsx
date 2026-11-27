import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import '../styles/concepts.css'
import Editor, { type OnMount } from '@monaco-editor/react'
import { Group, Panel, Separator } from 'react-resizable-panels'
import {
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Circle,
  CloudCheck,
  Code2,
  Download,
  ExternalLink,
  Files,
  History,
  LayoutPanelLeft,
  Lightbulb,
  Loader2,
  LockKeyhole,
  Maximize2,
  MessageSquare,
  PanelBottom,
  PanelLeftClose,
  Play,
  RotateCcw,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  Square,
  Terminal,
  X,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useWorkspace } from '../hooks/useWorkspace'
import { apiFetch, API_BASE_URL } from '../lib/supabase'
import { FileExplorer, getFileIcon } from '../components/workspace/FileExplorer'
import { AiSideChat } from '../components/workspace/AiSideChat'
import {
  NUDGE_MONACO_THEME,
  registerNudgeMonacoTheme,
} from '../lib/monacoTheme'
import type { Checkpoint, RuntimeResult } from '../types/workspace'
import '../styles/workbench.css'

export default function WorkspacePage() {
  const { projectId = '' } = useParams()
  const workspace = useWorkspace(projectId)
  const {
    session,
    files,
    activeFile: activePath,
    activeTask: taskId,
    sync,
    mutating,
  } = workspace
  const [tabs, setTabs] = useState<string[]>([])
  const [left, setLeft] = useState<'files' | 'tasks' | 'history'>('files')
  const [explorer, setExplorer] = useState(true)
  const [assistant, setAssistant] = useState(true)
  const [sideView, setSideView] = useState<'task' | 'mentor'>('task')
  const [previewExpanded, setPreviewExpanded] = useState(false)
  const [bottom, setBottom] = useState<'output' | 'checks' | 'preview' | null>(
    'output',
  )
  const [running, setRunning] = useState(false)
  const [checking, setChecking] = useState(false)
  const [chatting, setChatting] = useState(false)
  const [hinting, setHinting] = useState(false)
  const [runtime, setRuntime] = useState<RuntimeResult | null>(null)
  const [snapshots, setSnapshots] = useState<Checkpoint[]>([])
  const [cursor, setCursor] = useState({ line: 1, column: 1 })
  const [filter, setFilter] = useState('')
  const [confirm, setConfirm] = useState<{
    label: string
    description: string
    action: () => Promise<unknown>
  } | null>(null)
  const [notice, setNotice] = useState('')
  const showExplorer = () => {
    if (window.innerWidth < 950) setAssistant(false)
    setExplorer(true)
  }
  const toggleMentor = () => {
    if (!assistant && window.innerWidth < 950) setExplorer(false)
    setAssistant(!assistant)
  }
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null)
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null)
  const pendingHintLine = useRef<{ path: string; line: number } | null>(null)
  const hintDecoration = useRef<ReturnType<
    Parameters<OnMount>[0]['createDecorationsCollection']
  > | null>(null)
  const highlightHint = (editor: Parameters<OnMount>[0], line: number) => {
    hintDecoration.current?.clear()
    hintDecoration.current = editor.createDecorationsCollection([
      {
        range: {
          startLineNumber: line,
          startColumn: 1,
          endLineNumber: line,
          endColumn: 1,
        },
        options: { isWholeLine: true, className: 'mentor-hint-line' },
      },
    ])
    editor.setSelection({
      startLineNumber: line,
      startColumn: 1,
      endLineNumber: line,
      endColumn: editor.getModel()?.getLineMaxColumn(line) || 1,
    })
    editor.revealLineInCenter(line)
    editor.focus()
  }
  const layoutCleanup = useRef<(() => void) | null>(null)
  const saveRef = useRef(workspace.save)
  useEffect(() => {
    const resize = () => {
      if (window.innerWidth < 1100) setExplorer(false)
      if (window.innerWidth < 850) setAssistant(false)
    }
    resize()
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [])
  useEffect(() => {
    saveRef.current = workspace.save
  }, [workspace.save])
  const actionBusy = running || checking || mutating || chatting || hinting
  const file = files.find((f) => f.path === activePath) || files[0]
  const task =
    session?.project.tasks.find((t) => t.id === taskId) ||
    session?.project.tasks[0]
  const report = task ? session?.last_verification[task.id] : undefined
  const checkExecutionError = report?.execution_status === 'error'
  const stale =
    !!report &&
    (report.content_hash !== session?.content_hash ||
      workspace.dirtyPaths.size > 0)
  const visibleTabs = Array.from(
    new Set([...tabs, ...(file ? [file.path] : [])]),
  ).filter((path) => files.some((f) => f.path === path))
  const openFile = (path: string) => {
    workspace.selectFile(path)
    setTabs((prev) => [...new Set([...prev, path])])
  }
  const notifyError = (e: unknown) =>
    workspace.setError(
      e instanceof Error ? e.message : 'Something went wrong. Please retry.',
    )
  const loadHistory = async () => {
    try {
      setSnapshots(await apiFetch<Checkpoint[]>(`${workspace.base}/snapshots`))
    } catch (e) {
      notifyError(e)
    }
  }
  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault()
        void saveRef.current().catch(() => {})
      }
    }
    window.addEventListener('keydown', keyboard)
    return () => window.removeEventListener('keydown', keyboard)
  }, [])
  useEffect(
    () => () => {
      layoutCleanup.current?.()
      if (session?.session_id) {
        monacoRef.current?.editor
          .getModels()
          .forEach((model: { uri: { path: string }; dispose: () => void }) => {
            if (model.uri.path.startsWith(`/${session.session_id}/`))
              model.dispose()
          })
      }
    },
    [session?.session_id],
  )
  const onMount: OnMount = (editor, monaco) => {
    layoutCleanup.current?.()
    hintDecoration.current = null
    editorRef.current = editor
    monacoRef.current = monaco
    if (pendingHintLine.current?.path === file?.path) {
      highlightHint(editor, pendingHintLine.current.line)
      pendingHintLine.current = null
    }
    const cursorListener = editor.onDidChangeCursorPosition((e) =>
      setCursor({ line: e.position.lineNumber, column: e.position.column }),
    )
    // Defer editor layout outside ResizeObserver delivery so resizing panels
    // cannot create a synchronous observer/layout feedback loop.
    let frame = 0
    let previousWidth = 0
    let previousHeight = 0
    const container = editor.getDomNode()?.closest('.monaco-container')
    const resize = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(() => {
        const rect = container?.getBoundingClientRect()
        if (!rect) return
        const width = Math.floor(rect.width)
        const height = Math.floor(rect.height)
        if (
          width > 0 &&
          height > 0 &&
          (width !== previousWidth || height !== previousHeight)
        ) {
          previousWidth = width
          previousHeight = height
          editor.layout({ width, height })
        }
      })
    }
    const observer = new ResizeObserver(resize)
    if (container) observer.observe(container)
    resize()
    layoutCleanup.current = () => {
      observer.disconnect()
      window.cancelAnimationFrame(frame)
      cursorListener.dispose()
    }
  }
  const run = async () => {
    setRunning(true)
    setBottom('output')
    workspace.setError('')
    try {
      const saved = await workspace.save()
      const result = await apiFetch<RuntimeResult>(`${workspace.base}/run`, {
        method: 'POST',
        body: JSON.stringify({ expected_revision: saved.revision }),
      })
      setRuntime(result)
      if (result.preview_url) setBottom('preview')
    } catch (e) {
      notifyError(e)
    } finally {
      setRunning(false)
    }
  }
  const stop = async () => {
    try {
      await apiFetch(`${workspace.base}/run`, { method: 'DELETE' })
      setRuntime((prev) =>
        prev ? { ...prev, status: 'stopped', preview_url: undefined } : null,
      )
    } catch (e) {
      notifyError(e)
    }
  }
  const check = async () => {
    if (!task) return
    setChecking(true)
    setBottom('checks')
    workspace.setError('')
    try {
      await workspace.mutate('/verify', 'POST', { task_id: task.id })
    } catch {
      /* Error banner retains failure. */
    } finally {
      setChecking(false)
    }
  }
  if (!session || !task)
    return (
      <div className="brief-loading">
        {workspace.error ? (
          <>
            <p role="alert">{workspace.error}</p>
            <Link to={`/projects/${projectId}`}>Back to project brief</Link>
          </>
        ) : (
          <>
            <Loader2 className="spin" /> Opening your workspace…
          </>
        )}
      </div>
    )
  const completed = workspace.dirtyPaths.size ? [] : session.completed_task_ids
  const progress = Math.round(
    (completed.length / session.project.tasks.length) * 100,
  )
  return (
    <div className="workbench">
      <header className="wb-topbar">
        <Link
          to={`/projects/${projectId}`}
          className="nudge-wordmark"
          onClick={(event) => {
            if (
              workspace.dirtyPaths.size &&
              !window.confirm(
                'You have unsaved edits. A local recovery copy is available. Leave this workspace?',
              )
            )
              event.preventDefault()
          }}
        >
          <Sparkles size={20} /> nudge
        </Link>
        <span className="topbar-divider" />
        <Link className="project-location" to={`/projects/${projectId}`}>
          <Code2 size={15} />
          <span>{session.project.title}</span>
          <ChevronDown size={13} />
        </Link>
        <span className="workspace-label">WORKSPACE</span>
        <div className="topbar-actions">
          <span className={`sync-state ${sync}`}>
            <CloudCheck size={14} />
            {sync === 'saved'
              ? 'All changes saved'
              : sync === 'saving'
                ? 'Saving…'
                : sync === 'conflict'
                  ? 'Save conflict'
                  : 'Unsaved changes'}
          </span>
          <button
            className="icon-button"
            title="Export project as ZIP"
            aria-label="Export project as ZIP"
            onClick={() => void workspace.download().catch(notifyError)}
          >
            <Download size={17} />
          </button>
          <button
            className="secondary-button check-button"
            aria-label="Check task"
            disabled={actionBusy || sync === 'conflict'}
            onClick={() => void check()}
          >
            {checking ? (
              <Loader2 size={15} className="spin" />
            ) : (
              <ShieldCheck size={16} />
            )}
            <span>Check task</span>
          </button>
          {runtime?.status === 'running' ? (
            <button
              className="primary-button run-button"
              onClick={() => void stop()}
            >
              <Square size={13} fill="currentColor" />
              Stop
            </button>
          ) : (
            <button
              className="primary-button run-button"
              disabled={actionBusy || sync === 'conflict'}
              onClick={() => void run()}
            >
              {running ? (
                <Loader2 className="spin" size={15} />
              ) : (
                <Play size={14} fill="currentColor" />
              )}
              Run
            </button>
          )}
        </div>
      </header>
      {workspace.error && (
        <div className="wb-banner error" role="alert">
          <span>{workspace.error}</span>
          {sync === 'conflict' && (
            <button onClick={() => window.location.reload()}>
              Reload saved version
            </button>
          )}
          <button
            aria-label="Dismiss error"
            onClick={() => workspace.setError('')}
          >
            <X size={15} />
          </button>
        </div>
      )}
      {workspace.draft && (
        <div className="wb-banner">
          <History size={16} />
          <span>Unsaved work was recovered from this browser.</span>
          <button onClick={workspace.recover}>Restore local edits</button>
          <button onClick={workspace.discardDraft}>Keep server version</button>
        </div>
      )}
      {notice && (
        <div className="wb-banner success">
          <CheckCircle2 size={16} />
          <span>{notice}</span>
          <button
            onClick={() => setNotice('')}
            aria-label="Dismiss notification"
          >
            <X size={15} />
          </button>
        </div>
      )}
      <div className="wb-body">
        <nav className="activity-bar" aria-label="Workspace views">
          {[
            { id: 'files', icon: Files, label: 'Explorer' },
            { id: 'tasks', icon: BookOpen, label: 'Task roadmap' },
            { id: 'history', icon: History, label: 'Checkpoints' },
          ].map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              className={explorer && left === id ? 'active' : ''}
              title={label}
              aria-label={label}
              aria-pressed={explorer && left === id}
              onClick={() => {
                setLeft(id as typeof left)
                showExplorer()
                if (id === 'history') void loadHistory()
              }}
            >
              <Icon size={21} />
            </button>
          ))}
          <div className="activity-spacer" />
          <button
            title="Project brief"
            aria-label="View project brief"
            onClick={() =>
              window.open(`/projects/${projectId}`, '_blank', 'noopener')
            }
          >
            <GraduationIcon />
          </button>
          <button
            className={assistant ? 'active' : ''}
            title="Toggle mentor"
            aria-label="Toggle AI mentor"
            aria-pressed={assistant}
            onClick={() => toggleMentor()}
          >
            <Sparkles size={21} />
          </button>
        </nav>
        <Group orientation="horizontal" className="wb-panels">
          {explorer && (
            <>
              <Panel
                id="explorer"
                defaultSize="19%"
                minSize="170px"
                maxSize="32%"
              >
                <aside className="wb-explorer">
                  <div className="panel-title">
                    <span>
                      {left === 'files'
                        ? 'EXPLORER'
                        : left === 'tasks'
                          ? 'BUILD PLAN'
                          : 'CHECKPOINTS'}
                    </span>
                    <button
                      className="icon-button"
                      title="Hide sidebar"
                      aria-label="Hide sidebar"
                      onClick={() => setExplorer(false)}
                    >
                      <PanelLeftClose size={15} />
                    </button>
                  </div>
                  {left === 'files' ? (
                    <>
                      <label className="file-search">
                        <Search size={14} />
                        <input
                          placeholder="Find a file…"
                          aria-label="Filter files"
                          value={filter}
                          onChange={(e) => setFilter(e.target.value)}
                        />
                      </label>
                      <FileExplorer
                        projectId={projectId}
                        files={files.filter((f) =>
                          f.path.toLowerCase().includes(filter.toLowerCase()),
                        )}
                        activeFilePath={file?.path || ''}
                        dirtyPaths={workspace.dirtyPaths}
                        taskFilePaths={task.task_files.map((item) => item.path)}
                        onSelectFile={openFile}
                        onCreateFile={async (path) => {
                          await workspace.mutate(
                            '/files',
                            'POST',
                            { path },
                            true,
                          )
                        }}
                        onRenameFile={async (old_path, new_path) => {
                          await workspace.mutate(
                            '/files/rename',
                            'PATCH',
                            { old_path, new_path },
                            true,
                          )
                          setTabs((prev) =>
                            prev.map((p) => (p === old_path ? new_path : p)),
                          )
                        }}
                        onDeleteFile={async (path) => {
                          await workspace.mutate(
                            `/files?path=${encodeURIComponent(path)}`,
                            'DELETE',
                            {},
                            true,
                          )
                        }}
                      />
                    </>
                  ) : left === 'tasks' ? (
                    <div className="roadmap-list">
                      <div className="roadmap-summary">
                        <span>Your progress</span>
                        <strong>
                          {completed.length}/{session.project.tasks.length}
                        </strong>
                        <div className="progress-track">
                          <div style={{ width: `${progress}%` }} />
                        </div>
                      </div>
                      {session.project.tasks.map((t) => (
                        <button
                          key={t.id}
                          disabled={!session.unlocked_task_ids.includes(t.id)}
                          title={
                            !session.unlocked_task_ids.includes(t.id)
                              ? 'Complete the previous task to unlock this one'
                              : t.title
                          }
                          className={t.id === task.id ? 'selected' : ''}
                          onClick={() => {
                            workspace.selectTask(t.id)
                            openFile(t.target_file)
                          }}
                        >
                          {completed.includes(t.id) ? (
                            <CheckCircle2 size={17} className="green-text" />
                          ) : (
                            <span className="task-number">{t.order}</span>
                          )}
                          <span>
                            {t.order}. {t.title}
                            <small>
                              {session.unlocked_task_ids.includes(t.id)
                                ? `${t.validation_criteria.length} checks`
                                : 'Locked — finish the previous task'}
                            </small>
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="checkpoint-list">
                      <p>
                        Save a point you can return to. The latest 20
                        checkpoints are kept.
                      </p>
                      <button
                        className="secondary-button"
                        disabled={actionBusy}
                        onClick={() =>
                          void workspace
                            .mutate('/snapshots', 'POST')
                            .then(() => {
                              setNotice('Checkpoint saved.')
                              void loadHistory()
                            })
                            .catch(() => {})
                        }
                      >
                        <Save size={15} />
                        Save checkpoint
                      </button>
                      {snapshots.map((item) => (
                        <article key={item.id}>
                          <History size={15} />
                          <div>
                            <strong>{item.label}</strong>
                            <small>
                              Revision {item.revision} ·{' '}
                              {new Date(item.created_at).toLocaleDateString()}
                            </small>
                            <button
                              onClick={() =>
                                setConfirm({
                                  label: 'Restore checkpoint',
                                  description:
                                    'Your current files will be checkpointed before restoring this version.',
                                  action: async () => {
                                    await workspace.mutate(
                                      `/snapshots/${item.id}/restore`,
                                      'POST',
                                      {},
                                      true,
                                    )
                                    await loadHistory()
                                  },
                                })
                              }
                            >
                              Restore
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                  <div className="explorer-footer">
                    <span>
                      <LockKeyhole size={13} /> Private workspace
                    </span>
                    <span>v{session.project.version.slice(0, 7)}</span>
                  </div>
                </aside>
              </Panel>
              <Separator className="wb-separator" />
            </>
          )}
          <Panel
            id="editor"
            defaultSize={assistant ? '53%' : '81%'}
            minSize="280px"
          >
            <main className="wb-editor-column">
              <div
                className="editor-tabs"
                role="tablist"
                aria-label="Open files"
              >
                {!explorer && (
                  <button
                    className="icon-button"
                    title="Show explorer"
                    aria-label="Show explorer"
                    onClick={() => showExplorer()}
                  >
                    <LayoutPanelLeft size={16} />
                  </button>
                )}
                {visibleTabs.map((path) => (
                  <div
                    className={`editor-tab ${path === file?.path ? 'active' : ''}`}
                    key={path}
                  >
                    <button
                      role="tab"
                      aria-selected={path === file?.path}
                      onClick={() => openFile(path)}
                    >
                      {getFileIcon(path)}
                      <span>{path.split('/').pop()}</span>
                      {workspace.dirtyPaths.has(path) && (
                        <span className="dirty-dot" />
                      )}
                    </button>
                    <button
                      className="tab-close"
                      aria-label={`Close ${path}`}
                      onClick={() => {
                        const next = visibleTabs.filter((p) => p !== path)
                        if (!next.length) return
                        setTabs(next)
                        if (activePath === path)
                          workspace.selectFile(next[next.length - 1])
                      }}
                    >
                      <X size={13} />
                    </button>
                  </div>
                ))}
                <div className="tabs-spacer" />
                <button
                  className="icon-button"
                  title="Toggle mentor"
                  aria-label="Toggle mentor panel"
                  onClick={() => toggleMentor()}
                >
                  <MessageSquare size={16} />
                </button>
              </div>
              <div className="editor-breadcrumb">
                <span>{projectId}</span>
                <ChevronRight size={13} />
                <span>{file?.path}</span>
                {file?.read_only && (
                  <span className="readonly-label">
                    <LockKeyhole size={11} />
                    Read only
                  </span>
                )}
                <button
                  title="Focus editor"
                  aria-label="Focus editor"
                  onClick={() => editorRef.current?.focus()}
                >
                  <Maximize2 size={13} />
                </button>
              </div>
              <div className="task-ribbon">
                <span className="task-ribbon-icon">
                  <BookOpen size={16} />
                </span>
                <div>
                  <small>
                    CURRENT TASK · {task.order} OF{' '}
                    {session.project.tasks.length}
                  </small>
                  <strong>{task.title}</strong>
                </div>
                <button
                  onClick={() => {
                    setLeft('tasks')
                    showExplorer()
                  }}
                >
                  View plan
                  <ChevronRight size={13} />
                </button>
              </div>
              <Group orientation="vertical" className="editor-split">
                <Panel id="code" defaultSize="65%" minSize="140px">
                  <div className="monaco-container">
                    <Editor
                      key={`${session.session_id}:${file?.path}`}
                      keepCurrentModel
                      height="100%"
                      path={`file:///${session.session_id}/${file?.path.split('/').map(encodeURIComponent).join('/')}`}
                      language={file?.language}
                      value={file?.content}
                      theme={NUDGE_MONACO_THEME}
                      beforeMount={registerNudgeMonacoTheme}
                      onMount={onMount}
                      onChange={(value) => {
                        if (
                          file &&
                          editorRef.current?.getModel()?.uri.path ===
                            `/${session.session_id}/${file.path}`
                        ) {
                          workspace.edit(file.path, value ?? '')
                        }
                      }}
                      options={{
                        readOnly: !!file?.read_only || mutating,
                        fontSize: 14,
                        fontFamily: "'JetBrains Mono', Consolas, monospace",
                        lineHeight: 23,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        padding: { top: 20 },
                        automaticLayout: false,
                        tabSize: 4,
                        renderLineHighlight: 'gutter',
                        smoothScrolling: true,
                      }}
                    />
                  </div>
                </Panel>
                {bottom && (
                  <>
                    <Separator className="wb-horizontal-separator" />
                    <Panel id="output" defaultSize="35%" minSize="100px">
                      <section className="output-panel">
                        <div
                          className="output-tabs"
                          role="tablist"
                          aria-label="Run results"
                        >
                          {(['output', 'checks', 'preview'] as const).map(
                            (view) => (
                              <button
                                role="tab"
                                aria-selected={bottom === view}
                                className={bottom === view ? 'active' : ''}
                                key={view}
                                onClick={() => setBottom(view)}
                              >
                                {view === 'output' ? (
                                  <Terminal size={14} />
                                ) : view === 'checks' ? (
                                  <ShieldCheck size={14} />
                                ) : (
                                  <ExternalLink size={14} />
                                )}
                                {view === 'output'
                                  ? 'Output'
                                  : view === 'checks'
                                    ? 'Task checks'
                                    : 'Preview'}
                                {view === 'checks' && report && (
                                  <span>
                                    {checkExecutionError ? 'No verdict' : <>{
                                      report.criteria_results.filter(
                                        (c) => c.passed,
                                      ).length
                                    }
                                    /{task.validation_criteria.length}</>}
                                  </span>
                                )}
                              </button>
                            ),
                          )}
                          <span className="tabs-spacer" />
                          <button
                            className="icon-button"
                            aria-label="Hide output panel"
                            onClick={() => setBottom(null)}
                          >
                            <X size={15} />
                          </button>
                        </div>
                        <div
                          className={`output-content ${bottom === 'preview' ? 'preview-content' : ''}`}
                        >
                          {bottom === 'output' ? (
                            running ? (
                              <div className="output-empty">
                                <Loader2 className="spin" size={20} />
                                <p>Starting your isolated runtime…</p>
                              </div>
                            ) : runtime ? (
                              <>
                                <div className="run-meta">
                                  <span>Revision {runtime.revision}</span>
                                  <span>
                                    {runtime.status}
                                    {runtime.exit_code != null
                                      ? ` · exit ${runtime.exit_code}`
                                      : ''}
                                  </span>
                                  {runtime.revision !== session.revision && (
                                    <span className="amber-text">
                                      Newer edits are saved. Run again to
                                      update.
                                    </span>
                                  )}
                                </div>
                                <pre>
                                  {runtime.output ||
                                    'Application finished without console output.'}
                                </pre>
                              </>
                            ) : (
                              <div className="output-empty">
                                <Terminal size={22} />
                                <p>Your application output appears here.</p>
                                <span>
                                  Run your code to see it in action. Check task
                                  to test acceptance criteria.
                                </span>
                              </div>
                            )
                          ) : bottom === 'checks' ? (
                            checking ? (
                              <div className="output-empty">
                                <Loader2 className="spin" size={20} />
                                <p>Checking your implementation…</p>
                              </div>
                            ) : report ? (
                              <>
                                <div className="run-meta">
                                  <span
                                    className={
                                      stale || checkExecutionError
                                        ? 'amber-text'
                                        : report.passed_all
                                          ? 'green-text'
                                          : ''
                                    }
                                  >
                                    {stale
                                      ? 'Results from an earlier code version'
                                      : checkExecutionError
                                        ? 'Checks could not complete — no verdict yet'
                                      : report.passed_all
                                        ? 'All acceptance checks passed'
                                        : 'Keep going — some checks need work'}
                                  </span>
                                  <span>{report.execution_ms} ms</span>
                                </div>
                                {report.criteria_results.map((c) => (
                                  <div
                                    className={`criterion ${checkExecutionError ? '' : c.passed ? 'pass' : 'fail'}`}
                                    key={c.criterion}
                                  >
                                    {c.passed && !checkExecutionError ? (
                                      <CheckCircle2 size={16} />
                                    ) : (
                                      <Circle size={16} />
                                    )}
                                    <div>
                                      <strong>{c.criterion}</strong>
                                      <p>{checkExecutionError ? 'Not evaluated: the checker could not complete.' : c.reason}</p>
                                    </div>
                                  </div>
                                ))}
                                <div className="review-note">
                                  <Sparkles size={15} />
                                  {report.architectural_feedback}
                                </div>
                                <details>
                                  <summary>Execution logs</summary>
                                  <pre>{report.sandbox_output}</pre>
                                </details>
                              </>
                            ) : (
                              <div className="output-empty">
                                <ShieldCheck size={24} />
                                <p>No checks run yet.</p>
                                <span>
                                  Build your solution, then choose Check task.
                                </span>
                              </div>
                            )
                          ) : runtime?.status === 'running' &&
                            runtime.preview_url ? (
                            <>
                              <div className="preview-address">
                                <button
                                  className="preview-expand"
                                  aria-label="Expand application preview"
                                  title="Expand preview"
                                  onClick={() => setPreviewExpanded(true)}
                                >
                                  <Maximize2 size={13} />
                                </button>
                                <LockKeyhole size={12} />
                                <span>
                                  Isolated preview · revision {runtime.revision}
                                </span>
                                <button
                                  onClick={() => {
                                    const frame = document.getElementById(
                                      'application-preview',
                                    ) as HTMLIFrameElement | null
                                    if (frame) {
                                      const url = frame.getAttribute('src')
                                      if (url) frame.setAttribute('src', url)
                                    }
                                  }}
                                  aria-label="Refresh preview"
                                >
                                  <RotateCcw size={13} />
                                </button>
                              </div>
                              <iframe
                                id="application-preview"
                                title="Your running application"
                                src={`${API_BASE_URL}${runtime.preview_url}`}
                                sandbox="allow-scripts allow-forms"
                                referrerPolicy="no-referrer"
                              />
                            </>
                          ) : (
                            <div className="output-empty">
                              <Code2 size={24} />
                              <p>
                                {session.project.runtime.mode === 'web'
                                  ? 'Your application, brought to life.'
                                  : 'This project runs in the console.'}
                              </p>
                              <span>
                                {session.project.runtime.mode === 'web'
                                  ? 'Choose Run to start an interactive preview.'
                                  : 'Choose Run, then open Output to inspect the results.'}
                              </span>
                            </div>
                          )}
                        </div>
                      </section>
                    </Panel>
                  </>
                )}
              </Group>
            </main>
          </Panel>
          {assistant && (
            <>
              <Separator className="wb-separator" />
              <Panel
                id="mentor"
                defaultSize="28%"
                minSize="270px"
                maxSize="45%"
              >
                <aside className="mentor-panel">
                  <div className="mentor-panel-heading">
                    <Sparkles size={17} />
                    <strong>Your build companion</strong>
                    <button
                      className="icon-button"
                      aria-label="Hide mentor panel"
                      onClick={() => setAssistant(false)}
                    >
                      <X size={15} />
                    </button>
                  </div>
                  <div
                    className="mentor-view-tabs"
                    role="tablist"
                    aria-label="Companion view"
                  >
                    <button
                      role="tab"
                      aria-selected={sideView === 'task'}
                      className={sideView === 'task' ? 'active' : ''}
                      onClick={() => setSideView('task')}
                    >
                      Task brief
                    </button>
                    <button
                      role="tab"
                      aria-selected={sideView === 'mentor'}
                      className={sideView === 'mentor' ? 'active' : ''}
                      onClick={() => setSideView('mentor')}
                    >
                      <MessageSquare size={13} /> AI mentor
                    </button>
                  </div>
                  {sideView === 'task' && (
                    <>
                      <details className="task-brief-panel" open>
                        <summary>
                          <span>
                            <BookOpen size={15} />
                            {task.title}
                          </span>
                          <ChevronDown size={14} />
                        </summary>
                        <div className="markdown-content">
                          <p className="task-objective">{task.objective}</p>
                          {task.concept_markdown && <Link
                            className="learn-concept-link"
                            to={`/projects/${session.project.id}/tasks/${task.id}/learn`}
                            target="_blank" rel="noopener noreferrer"
                          ><BookOpen size={16} /> Learn the concept <ExternalLink size={14} /><span className="sr-only"> (opens in a new tab)</span></Link>}
                          {task.estimated_time && <small className="phase-roadmap-meta">Estimated build time: {task.estimated_time}</small>}
                          <section
                            className="task-files"
                            aria-label="Files for this task"
                          >
                            <h4>Files for this task</h4>
                            <p>
                              Open a file below. Edit the marked file and use
                              the others to understand how it fits together.
                            </p>
                            <div>
                              {task.task_files.map((item) => (
                                <button
                                  key={item.path}
                                  type="button"
                                  className={
                                    item.path === file?.path ? 'active' : ''
                                  }
                                  disabled={
                                    !files.some(
                                      (entry) => entry.path === item.path,
                                    )
                                  }
                                  onClick={() => openFile(item.path)}
                                  aria-label={`Open ${item.path} — ${item.purpose === 'edit' ? 'edit this file' : 'read for context'}`}
                                >
                                  {getFileIcon(item.path)}
                                  <code>{item.path}</code>
                                  <small>
                                    {item.purpose === 'edit' ? 'Edit' : 'Read'}
                                  </small>
                                </button>
                              ))}
                            </div>
                          </section>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {task.instructions}
                          </ReactMarkdown>
                          <h4>Acceptance criteria</h4>
                          <ul className="acceptance-list">
                            {task.validation_criteria.map((c, index) => (
                              <li key={c}>
                                {!stale &&
                                report?.criteria_results[index]?.passed ? (
                                  <CheckCircle2
                                    size={15}
                                    className="green-text"
                                  />
                                ) : (
                                  <Circle size={15} />
                                )}
                                <span>{c}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </details>
                      <div className="task-help">
                        <Lightbulb size={17} />
                        <p>
                          Stuck on a step?
                          <span>
                            Your mentor can help you reason through it.
                          </span>
                        </p>
                        <button onClick={() => setSideView('mentor')}>
                          Ask Nudge
                        </button>
                      </div>
                    </>
                  )}
                  {sideView === 'mentor' && (
                    <AiSideChat
                      activeFilePath={file?.path || ''}
                      activeTask={task}
                      hintLevel={session.hint_levels[task.id] || 0}
                      messages={session.chat_messages.filter(
                        (m) => !m.task_id || m.task_id === task.id,
                      )}
                      sendingChat={chatting}
                      requestingHint={hinting}
                      streamingText={
                        workspace.streamingReply?.taskId === task.id
                          ? workspace.streamingReply.text
                          : ''
                      }
                      onRevealCode={(path, line) => {
                        const target = files.find((item) => item.path === path)
                        if (
                          !target ||
                          line > target.content.split('\n').length
                        ) {
                          setNotice(
                            'That hint refers to a line unavailable in the current files. Ask for an updated hint.',
                          )
                          return
                        }
                        if (file?.path === path && editorRef.current) {
                          highlightHint(editorRef.current, line)
                        } else {
                          pendingHintLine.current = { path, line }
                          openFile(path)
                        }
                      }}
                      onSendMessage={async (message) => {
                        setChatting(true)
                        try {
                          await workspace.streamMentor('/chat', {
                            task_id: task.id,
                            active_file_path: activePath,
                            message,
                          })
                        } finally {
                          setChatting(false)
                        }
                      }}
                      onRequestHint={async () => {
                        setHinting(true)
                        try {
                          await workspace.streamMentor('/nudge', {
                            task_id: task.id,
                            active_file_path: activePath,
                          })
                        } finally {
                          setHinting(false)
                        }
                      }}
                    />
                  )}
                </aside>
              </Panel>
            </>
          )}
        </Group>
      </div>
      <footer className="wb-statusbar">
        <div>
          <span>
            <Code2 size={13} />
            {session.project.category}
          </span>
          <button
            onClick={() => {
              setLeft('tasks')
              showExplorer()
            }}
          >
            <CheckCircle2 size={13} />
            {completed.length}/{session.project.tasks.length} tasks
          </button>
        </div>
        <div>
          <button
            onClick={() =>
              setConfirm({
                label: 'Reset workspace',
                description:
                  'Start again with the latest course and its starter files? Task progress is cleared. A recovery checkpoint of your current files will be saved first. Hints are kept.',
                action: () =>
                  workspace.mutate(
                    '/reset',
                    'POST',
                    { reset_progress: false },
                    true,
                  ),
              })
            }
          >
            <RotateCcw size={12} />
            Reset files
          </button>
          <button onClick={() => setBottom(bottom ? null : 'output')}>
            <PanelBottom size={14} />
            Panel
          </button>
          <span>
            Ln {cursor.line}, Col {cursor.column}
          </span>
          <span>{file?.language}</span>
          <span>UTF-8</span>
        </div>
      </footer>
      {previewExpanded && runtime?.preview_url && (
        <div className="modal-backdrop">
          <section
            className="preview-popout"
            role="dialog"
            aria-modal="true"
            aria-label="Expanded application preview"
          >
            <header>
              <Code2 size={16} />
              <span>Your application ? revision {runtime.revision}</span>
              <button
                autoFocus
                aria-label="Close expanded preview"
                onClick={() => setPreviewExpanded(false)}
              >
                <X size={18} />
              </button>
            </header>
            <iframe
              title="Expanded running application"
              src={`${API_BASE_URL}${runtime.preview_url}`}
              sandbox="allow-scripts allow-forms"
              referrerPolicy="no-referrer"
            />
          </section>
        </div>
      )}
      {confirm && (
        <div className="modal-backdrop" onClick={() => setConfirm(null)}>
          <section
            className="wb-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            onClick={(e) => e.stopPropagation()}
          >
            <History size={25} />
            <h2 id="confirm-title">{confirm.label}</h2>
            <p>{confirm.description}</p>
            <div>
              <button
                className="secondary-button"
                onClick={() => setConfirm(null)}
              >
                Cancel
              </button>
              <button
                className="primary-button"
                onClick={() => {
                  const action = confirm.action
                  setConfirm(null)
                  void action().catch(notifyError)
                }}
              >
                {confirm.label}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

function GraduationIcon() {
  return <Lightbulb size={20} />
}
