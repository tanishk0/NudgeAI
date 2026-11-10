import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Editor, { type OnMount } from '@monaco-editor/react'
import { Group, Panel, Separator } from 'react-resizable-panels'
import {
  CheckCircle2,
  ChevronRight,
  CloudCheck,
  Loader2,
  Lock,
  Play,
  RotateCcw,
  Terminal,
  X,
  FolderGit2,
} from 'lucide-react'
import { apiFetch } from '../lib/supabase'
import { NUDGE_MONACO_THEME, registerNudgeMonacoTheme } from '../lib/monacoTheme'
import { FileExplorer, getFileIcon } from '../components/workspace/FileExplorer'
import { TaskHeaderBar } from '../components/workspace/TaskHeaderBar'
import { ConsoleDrawer } from '../components/workspace/ConsoleDrawer'
import { AiSideChat } from '../components/workspace/AiSideChat'
import type {
  WorkspaceFile,
  WorkspaceSessionResponse,
  TaskVerificationReport,
} from '../types/workspace'
import type { ProjectSummary } from './ProjectsHub'

export function WorkspacePage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  const [sessionData, setSessionData] = useState<WorkspaceSessionResponse | null>(
    null
  )
  const [allProjects, setAllProjects] = useState<ProjectSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Local editor state
  const [files, setFiles] = useState<WorkspaceFile[]>([])
  const [openTabs, setOpenTabs] = useState<string[]>([])
  const [activeFilePath, setActiveFilePath] = useState<string>('')
  const [activeTaskId, setActiveTaskId] = useState<string>('')
  const [dirtyPaths, setDirtyPaths] = useState<Set<string>>(new Set())
  const [syncStatus, setSyncStatus] = useState<'saved' | 'saving' | 'unsaved'>(
    'saved'
  )

  // Cursor position for bottom status bar
  const [cursorPos, setCursorPos] = useState<{ line: number; column: number }>({
    line: 1,
    column: 1,
  })

  // Bottom Console & Verification state
  const [consoleOpen, setConsoleOpen] = useState(false)
  const [runningVerify, setRunningVerify] = useState(false)

  // AI Side Chat loading states
  const [sendingChat, setSendingChat] = useState(false)
  const [requestingHint, setRequestingHint] = useState(false)

  const saveTimerRef = useRef<number | null>(null)

  // Fetch project summaries for the top Project Switcher dropdown
  useEffect(() => {
    apiFetch<ProjectSummary[]>('/api/projects')
      .then(setAllProjects)
      .catch(() => {})
  }, [])

  // Load workspace session from PostgreSQL
  useEffect(() => {
    if (!projectId) return
    let active = true
    setLoading(true)
    setError(null)

    apiFetch<WorkspaceSessionResponse>(`/api/workspace/${projectId}`)
      .then((data) => {
        if (!active) return
        setSessionData(data)
        setFiles(data.files)
        setActiveFilePath(data.active_file_path)
        setActiveTaskId(data.active_task_id)
        setOpenTabs(data.files.map((f) => f.path))
        setDirtyPaths(new Set())
        setSyncStatus('saved')
      })
      .catch((err: Error) => {
        if (!active) return
        setError(err.message || 'Failed to load workspace session.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [projectId])

  // Persist workspace state to PostgreSQL
  const persistState = useCallback(
    async (
      nextFiles: WorkspaceFile[],
      nextActiveFile: string,
      nextActiveTask: string
    ) => {
      if (!projectId) return
      setSyncStatus('saving')
      try {
        const updated = await apiFetch<WorkspaceSessionResponse>(
          `/api/workspace/${projectId}/state`,
          {
            method: 'PUT',
            body: JSON.stringify({
              files: nextFiles,
              active_file_path: nextActiveFile,
              active_task_id: nextActiveTask,
            }),
          }
        )
        setSessionData(updated)
        setDirtyPaths(new Set())
        setSyncStatus('saved')
      } catch (err) {
        console.error('[Workspace Sync Error]:', err)
        setSyncStatus('unsaved')
      }
    },
    [projectId]
  )

  const scheduleAutoSave = useCallback(
    (
      nextFiles: WorkspaceFile[],
      nextActiveFile: string,
      nextActiveTask: string
    ) => {
      setSyncStatus('unsaved')
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current)
      }
      saveTimerRef.current = window.setTimeout(() => {
        void persistState(nextFiles, nextActiveFile, nextActiveTask)
      }, 900)
    },
    [persistState]
  )

  const activeFile = useMemo(
    () => files.find((f) => f.path === activeFilePath) || files[0] || null,
    [files, activeFilePath]
  )

  const activeTask = useMemo(() => {
    const tasks = sessionData?.project.tasks || []
    return tasks.find((t) => t.id === activeTaskId) || tasks[0] || null
  }, [sessionData, activeTaskId])

  const handleSelectFile = (path: string) => {
    if (!openTabs.includes(path)) {
      setOpenTabs((prev) => [...prev, path])
    }
    setActiveFilePath(path)
    void persistState(files, path, activeTaskId)
  }

  const handleCloseTab = (path: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (openTabs.length <= 1) return
    const nextTabs = openTabs.filter((t) => t !== path)
    setOpenTabs(nextTabs)
    if (activeFilePath === path) {
      const nextActive = nextTabs[nextTabs.length - 1]
      setActiveFilePath(nextActive)
      void persistState(files, nextActive, activeTaskId)
    }
  }

  const handleSelectTask = (taskId: string) => {
    setActiveTaskId(taskId)
    void persistState(files, activeFilePath, taskId)
  }

  const handleEditorChange = (value: string | undefined) => {
    if (!activeFile || activeFile.read_only) return
    const newContent = value ?? ''
    const nextFiles = files.map((f) =>
      f.path === activeFile.path ? { ...f, content: newContent } : f
    )
    setFiles(nextFiles)
    setDirtyPaths((prev) => {
      const copy = new Set(prev)
      copy.add(activeFile.path)
      return copy
    })
    scheduleAutoSave(nextFiles, activeFilePath, activeTaskId)
  }

  const handleEditorMount: OnMount = (editor, monaco) => {
    editor.onDidChangeCursorPosition((e) => {
      setCursorPos({
        line: e.position.lineNumber,
        column: e.position.column,
      })
    })

    // Ctrl+S / Cmd+S manual save command
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current)
      }
      void persistState(files, activeFilePath, activeTaskId)
    })
  }

  // File tree CRUD operations
  const handleCreateFile = async (newPath: string) => {
    if (!projectId) return
    const updated = await apiFetch<WorkspaceSessionResponse>(
      `/api/workspace/${projectId}/files`,
      {
        method: 'POST',
        body: JSON.stringify({ path: newPath, content: '' }),
      }
    )
    setSessionData(updated)
    setFiles(updated.files)
    setActiveFilePath(updated.active_file_path)
    if (!openTabs.includes(updated.active_file_path)) {
      setOpenTabs((prev) => [...prev, updated.active_file_path])
    }
  }

  const handleRenameFile = async (oldPath: string, newPath: string) => {
    if (!projectId) return
    const updated = await apiFetch<WorkspaceSessionResponse>(
      `/api/workspace/${projectId}/files/rename`,
      {
        method: 'PATCH',
        body: JSON.stringify({ old_path: oldPath, new_path: newPath }),
      }
    )
    setSessionData(updated)
    setFiles(updated.files)
    setActiveFilePath(updated.active_file_path)
    setOpenTabs((prev) => prev.map((t) => (t === oldPath ? newPath : t)))
  }

  const handleDeleteFile = async (path: string) => {
    if (!projectId) return
    const updated = await apiFetch<WorkspaceSessionResponse>(
      `/api/workspace/${projectId}/files?path=${encodeURIComponent(path)}`,
      {
        method: 'DELETE',
      }
    )
    setSessionData(updated)
    setFiles(updated.files)
    setActiveFilePath(updated.active_file_path)
    setOpenTabs((prev) => {
      const remaining = prev.filter((t) => t !== path)
      return remaining.length > 0 ? remaining : [updated.active_file_path]
    })
  }

  const handleResetWorkspace = async () => {
    if (!projectId) return
    if (
      !window.confirm(
        'Reset all starter files back to their original code? (Your task progress and hints will be preserved.)'
      )
    ) {
      return
    }
    const updated = await apiFetch<WorkspaceSessionResponse>(
      `/api/workspace/${projectId}/reset`,
      {
        method: 'POST',
        body: JSON.stringify({ reset_progress: false }),
      }
    )
    setSessionData(updated)
    setFiles(updated.files)
    setActiveFilePath(updated.active_file_path)
    setDirtyPaths(new Set())
    setSyncStatus('saved')
  }

  // Verification handler (calls backend /verify endpoint when wired in Step 5)
  const handleRunAndVerify = async () => {
    if (!projectId || !activeTask) return
    setConsoleOpen(true)
    setRunningVerify(true)

    try {
      // Save latest editor state first
      await persistState(files, activeFilePath, activeTaskId)

      const updated = await apiFetch<WorkspaceSessionResponse>(
        `/api/workspace/${projectId}/verify`,
        {
          method: 'POST',
          body: JSON.stringify({
            task_id: activeTask.id,
            files,
          }),
        }
      )
      setSessionData(updated)
    } catch (err) {
      // Fallback report if Step 5 endpoint is not yet attached
      const fallbackReport: TaskVerificationReport = {
        task_id: activeTask.id,
        passed_all: false,
        sandbox_passed: false,
        sandbox_output:
          err instanceof Error
            ? `Verification runner message: ${err.message}`
            : 'Verification endpoint not yet active.',
        execution_ms: 12,
        criteria_results: activeTask.validation_criteria.map((c) => ({
          criterion: c,
          passed: false,
          reason: 'Ready for Step 5 verification engine.',
        })),
        architectural_feedback:
          'Step 5 will connect the Two-Layer Python Sandbox + NVIDIA NIM Evaluator to grade each criterion.',
      }
      setSessionData((prev) =>
        prev
          ? {
              ...prev,
              last_verification: {
                ...prev.last_verification,
                [activeTask.id]: fallbackReport,
              },
            }
          : prev
      )
    } finally {
      setRunningVerify(false)
    }
  }

  // AI Side Chat & Progressive Nudge handlers (connects to Step 6 endpoints)
  const handleSendChatMessage = async (message: string) => {
    if (!projectId || !activeTask) return
    setSendingChat(true)
    try {
      await persistState(files, activeFilePath, activeTaskId)
      const updated = await apiFetch<WorkspaceSessionResponse>(
        `/api/workspace/${projectId}/chat`,
        {
          method: 'POST',
          body: JSON.stringify({
            task_id: activeTask.id,
            active_file_path: activeFilePath,
            message,
            files,
          }),
        }
      )
      setSessionData(updated)
    } catch (err) {
      console.warn('[Chat API pending Step 6]:', err)
    } finally {
      setSendingChat(false)
    }
  }

  const handleRequestHint = async () => {
    if (!projectId || !activeTask) return
    setRequestingHint(true)
    try {
      await persistState(files, activeFilePath, activeTaskId)
      const updated = await apiFetch<WorkspaceSessionResponse>(
        `/api/workspace/${projectId}/nudge`,
        {
          method: 'POST',
          body: JSON.stringify({
            task_id: activeTask.id,
            active_file_path: activeFilePath,
            files,
          }),
        }
      )
      setSessionData(updated)
    } catch (err) {
      console.warn('[Nudge API pending Step 6]:', err)
    } finally {
      setRequestingHint(false)
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[#0b0c10] text-[#cdd6f4]">
        <div className="flex items-center gap-3 text-sm">
          <Loader2 className="h-5 w-5 animate-spin text-[#7aa2f7]" />
          <span>Loading Nudge IDE Workspace...</span>
        </div>
      </div>
    )
  }

  if (error || !sessionData || !activeTask) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center bg-[#0b0c10] text-white px-6 text-center">
        <p className="text-sm text-[#f38ba8] font-semibold">
          {error || 'Workspace could not be initialized.'}
        </p>
        <Link
          to="/projects"
          className="mt-4 rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-xs hover:bg-white/10"
        >
          &larr; Return to Projects Hub
        </Link>
      </div>
    )
  }

  const currentHintLevel = sessionData.hint_levels[activeTask.id] ?? 0
  const currentVerification = sessionData.last_verification[activeTask.id]

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#0b0c10] text-[#cdd6f4]">
      {/* 1. Top IDE Title Bar (42px) */}
      <header className="flex h-[42px] shrink-0 items-center justify-between border-b border-white/[0.07] bg-[#0b0c10] px-3.5 select-none">
        {/* Left: Brand + Project Switcher */}
        <div className="flex items-center gap-3 min-w-0">
          <Link
            to="/projects"
            title="Back to Projects Hub"
            className="inline-flex items-center gap-2 text-white/90 hover:text-white transition-colors"
          >
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              className="h-4 w-4 text-[#ffb86c]"
            >
              <path d="M12 1.5C12.7 7.1 16.9 11.3 22.5 12C16.9 12.7 12.7 16.9 12 22.5C11.3 16.9 7.1 12.7 1.5 12C7.1 11.3 11.3 7.1 12 1.5Z" />
            </svg>
            <span className="font-sans text-sm font-semibold tracking-tight">
              Nudge
            </span>
          </Link>

          <span className="text-white/20">/</span>

          {/* Project Switcher Dropdown */}
          <div className="relative flex items-center gap-1.5">
            <FolderGit2 className="h-3.5 w-3.5 text-[#7aa2f7]" />
            <select
              value={sessionData.project.id}
              onChange={(e) => navigate(`/workspace/${e.target.value}`)}
              className="rounded-lg border border-white/[0.08] bg-[#14151f] px-2.5 py-1 text-xs font-medium text-white focus:border-[#7aa2f7] focus:outline-none cursor-pointer"
            >
              {allProjects.length > 0 ? (
                allProjects.map((p) => (
                  <option key={p.id} value={p.id} className="bg-[#14151f]">
                    {p.title}
                  </option>
                ))
              ) : (
                <option value={sessionData.project.id}>
                  {sessionData.project.title}
                </option>
              )}
            </select>
          </div>
        </div>

        {/* Right: Sync Status + Reset + Run & Verify */}
        <div className="flex items-center gap-2.5">
          {/* Sync Pill */}
          <div className="hidden md:flex items-center gap-1.5 rounded-md border border-white/[0.06] bg-[#12131c] px-2.5 py-1 text-[11px] text-white/60">
            {syncStatus === 'saving' ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin text-[#7aa2f7]" />
                <span>Saving...</span>
              </>
            ) : syncStatus === 'unsaved' ? (
              <>
                <span className="h-2 w-2 rounded-full bg-[#ffb86c]" />
                <span>Unsaved edits</span>
              </>
            ) : (
              <>
                <CloudCheck className="h-3.5 w-3.5 text-[#a6e3a1]" />
                <span>Synced</span>
              </>
            )}
          </div>

          <button
            type="button"
            onClick={() => void handleResetWorkspace()}
            title="Reset files to starter code"
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-[#14151f] px-2.5 py-1 text-xs font-medium text-white/75 hover:bg-white/[0.08] hover:text-white transition-colors cursor-pointer"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Reset</span>
          </button>

          <button
            type="button"
            disabled={runningVerify}
            onClick={() => void handleRunAndVerify()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#a6e3a1] px-3 py-1 text-xs font-semibold text-[#0b0c10] shadow-[0_0_20px_rgba(166,227,161,0.25)] transition-all hover:bg-[#a6e3a1]/90 disabled:opacity-50 cursor-pointer"
          >
            {runningVerify ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5 fill-current" />
            )}
            <span>Run &amp; Verify</span>
          </button>
        </div>
      </header>

      {/* 2. Main 3-Column Resizable IDE Body */}
      <div className="flex-1 min-h-0">
        <Group orientation="horizontal" className="h-full w-full">
          {/* Left Panel: File Explorer */}
          <Panel
            id="explorer-panel"
            defaultSize="18%"
            minSize="13%"
            maxSize="30%"
          >
            <FileExplorer
              projectId={sessionData.project.id}
              files={files}
              activeFilePath={activeFile?.path || ''}
              dirtyPaths={dirtyPaths}
              onSelectFile={handleSelectFile}
              onCreateFile={handleCreateFile}
              onRenameFile={handleRenameFile}
              onDeleteFile={handleDeleteFile}
            />
          </Panel>

          <Separator className="w-[1px] bg-white/[0.07] hover:bg-[#7aa2f7] transition-colors" />

          {/* Center Panel: Compact Task Header + Tabbed Monaco Editor + Bottom Console */}
          <Panel id="editor-panel" defaultSize="54%" minSize="35%">
            <div className="flex h-full flex-col bg-[#14151f] min-w-0">
              {/* Compact Task Bar directly above Editor */}
              <TaskHeaderBar
                tasks={sessionData.project.tasks}
                activeTask={activeTask}
                completedTaskIds={sessionData.completed_task_ids}
                verification={currentVerification}
                aiFailureMode={sessionData.project.ai_failure_mode}
                onSelectTask={handleSelectTask}
                onSelectTargetFile={handleSelectFile}
              />

              {/* Multi-File Editor Tab Bar */}
              <div className="flex h-9 shrink-0 items-center overflow-x-auto border-b border-white/[0.06] bg-[#11121a] select-none">
                {openTabs.map((tabPath) => {
                  const fileObj = files.find((f) => f.path === tabPath)
                  if (!fileObj) return null
                  const isActive = fileObj.path === activeFile?.path
                  const isDirty = dirtyPaths.has(fileObj.path)

                  return (
                    <div
                      key={fileObj.path}
                      onClick={() => handleSelectFile(fileObj.path)}
                      className={`group flex h-full items-center gap-2 border-r border-white/[0.06] px-3 text-xs transition-colors cursor-pointer ${
                        isActive
                          ? 'bg-[#14151f] text-white border-t-2 border-t-[#7aa2f7]'
                          : 'bg-[#11121a] text-white/55 hover:bg-[#14151f]/60 hover:text-white/85 border-t-2 border-t-transparent'
                      }`}
                    >
                      {getFileIcon(fileObj.path)}
                      <span className="font-mono text-[12px]">
                        {fileObj.path}
                      </span>
                      {fileObj.read_only && (
                        <Lock className="h-3 w-3 text-white/35" />
                      )}
                      {isDirty && (
                        <span className="h-2 w-2 rounded-full bg-[#ffb86c]" />
                      )}
                      {openTabs.length > 1 && (
                        <button
                          type="button"
                          onClick={(e) => handleCloseTab(fileObj.path, e)}
                          className="ml-1 rounded p-0.5 text-white/35 opacity-0 group-hover:opacity-100 hover:bg-white/10 hover:text-white transition-all cursor-pointer"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Breadcrumb & Read-Only Indicator Bar */}
              {activeFile && (
                <div className="flex h-6 shrink-0 items-center justify-between border-b border-white/[0.04] bg-[#14151f] px-3.5 text-[11px] text-white/45 select-none">
                  <div className="flex items-center gap-1 font-mono">
                    <span>{sessionData.project.id}</span>
                    <ChevronRight className="h-3 w-3 text-white/30" />
                    <span className="text-white/80">{activeFile.path}</span>
                  </div>
                  {activeFile.read_only && (
                    <span className="inline-flex items-center gap-1 rounded bg-white/[0.06] px-1.5 py-0.2 font-mono text-[10px] text-[#cba6f7]">
                      <Lock className="h-2.5 w-2.5" />
                      READ-ONLY REFERENCE
                    </span>
                  )}
                </div>
              )}

              {/* Monaco Code Editor */}
              <div className="flex-1 min-h-0 relative">
                {activeFile ? (
                  <Editor
                    height="100%"
                    path={activeFile.path}
                    language={activeFile.language}
                    value={activeFile.content}
                    theme={NUDGE_MONACO_THEME}
                    beforeMount={registerNudgeMonacoTheme}
                    onMount={handleEditorMount}
                    onChange={handleEditorChange}
                    options={{
                      readOnly: activeFile.read_only,
                      fontSize: 13.5,
                      fontFamily:
                        "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                      fontLigatures: true,
                      lineHeight: 21,
                      minimap: { enabled: false },
                      scrollBeyondLastLine: false,
                      smoothScrolling: true,
                      cursorBlinking: 'smooth',
                      cursorSmoothCaretAnimation: 'on',
                      renderLineHighlight: 'all',
                      padding: { top: 14, bottom: 14 },
                      bracketPairColorization: { enabled: true },
                      automaticLayout: true,
                      tabSize: 4,
                    }}
                  />
                ) : null}
              </div>

              {/* Collapsible Bottom Console Drawer */}
              <ConsoleDrawer
                open={consoleOpen}
                running={runningVerify}
                report={currentVerification}
                onToggle={() => setConsoleOpen(false)}
                onClear={() => {
                  setSessionData((prev) => {
                    if (!prev) return prev
                    const nextVerif = { ...prev.last_verification }
                    delete nextVerif[activeTask.id]
                    return { ...prev, last_verification: nextVerif }
                  })
                }}
              />
            </div>
          </Panel>

          <Separator className="w-[1px] bg-white/[0.07] hover:bg-[#7aa2f7] transition-colors" />

          {/* Right Panel: AI Side Chat & 4-Step Progressive Hints */}
          <Panel
            id="ai-chat-panel"
            defaultSize="28%"
            minSize="22%"
            maxSize="42%"
          >
            <AiSideChat
              activeFilePath={activeFile?.path || ''}
              activeTask={activeTask}
              hintLevel={currentHintLevel}
              messages={sessionData.chat_messages}
              sendingChat={sendingChat}
              requestingHint={requestingHint}
              onSendMessage={handleSendChatMessage}
              onRequestHint={handleRequestHint}
            />
          </Panel>
        </Group>
      </div>

      {/* 3. Bottom IDE Status Bar (24px) */}
      <footer className="flex h-6 shrink-0 items-center justify-between border-t border-white/[0.07] bg-[#0b0c10] px-3 font-mono text-[11px] text-white/55 select-none">
        <div className="flex items-center gap-4">
          <span className="inline-flex items-center gap-1.5 text-[#a6e3a1]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#a6e3a1]" />
            PostgreSQL Connected
          </span>

          <span className="inline-flex items-center gap-1 text-white/70">
            <CheckCircle2 className="h-3 w-3 text-[#7aa2f7]" />
            Tasks: {sessionData.completed_task_ids.length}/
            {sessionData.project.tasks.length} Passed
          </span>

          <button
            type="button"
            onClick={() => setConsoleOpen((prev) => !prev)}
            className={`inline-flex items-center gap-1 rounded px-1.5 py-0.2 transition-colors cursor-pointer ${
              consoleOpen
                ? 'bg-[#7aa2f7]/20 text-[#7aa2f7]'
                : 'hover:text-white'
            }`}
          >
            <Terminal className="h-3 w-3" />
            <span>Console</span>
          </button>
        </div>

        <div className="flex items-center gap-4">
          <span>
            Ln {cursorPos.line}, Col {cursorPos.column}
          </span>
          <span className="hidden sm:inline">UTF-8</span>
          <span className="uppercase text-[#cba6f7]">
            {activeFile?.language || 'python'}
          </span>
          <span className="hidden md:inline text-[#ffb86c]">NVIDIA NIM</span>
        </div>
      </footer>
    </div>
  )
}

export default WorkspacePage

