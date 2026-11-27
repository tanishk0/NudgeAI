import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, apiFetch, apiRequest } from '../lib/supabase'
import { readMentorStream } from '../lib/mentor-stream'
import { useAuth } from '../context/AuthContext'
import type {
  WorkspaceFile,
  WorkspaceSessionResponse,
} from '../types/workspace'

type Sync = 'saved' | 'saving' | 'unsaved' | 'conflict'
const signature = (files: WorkspaceFile[]) =>
  JSON.stringify(files.map((f) => [f.path, f.content]).sort())

export function useWorkspace(projectId: string) {
  const { user } = useAuth()
  const [session, setSession] = useState<WorkspaceSessionResponse | null>(null)
  const [files, setFiles] = useState<WorkspaceFile[]>([])
  const [activeFile, setActiveFile] = useState('')
  const [activeTask, setActiveTask] = useState('')
  const [sync, setSync] = useState<Sync>('saved')
  const [error, setError] = useState('')
  const [mutating, setMutating] = useState(false)
  const [draft, setDraft] = useState<WorkspaceFile[] | null>(null)
  const [streamingReply, setStreamingReply] = useState<{
    taskId: string
    text: string
  } | null>(null)
  const streamController = useRef<AbortController | null>(null)
  const ref = useRef({
    files: [] as WorkspaceFile[],
    activeFile: '',
    activeTask: '',
    revision: 0,
    saved: '',
    loaded: false,
    conflict: false,
    mutating: false,
    mutationCount: 0,
  })
  const queue = useRef<Promise<unknown>>(Promise.resolve())
  const alive = useRef(true)
  const key = `nudge:draft:${user?.id}:${projectId}`
  const base = `/api/workspace/${projectId}`
  const remember = useCallback(() => {
    try {
      localStorage.setItem(
        key,
        JSON.stringify({
          files: ref.current.files,
          revision: ref.current.revision,
        }),
      )
    } catch {
      /* Server save remains available if browser storage is full. */
    }
  }, [key])
  const apply = useCallback(
    (data: WorkspaceSessionResponse, replaceFiles = false) => {
      if (!alive.current) return
      ref.current.revision = data.revision
      ref.current.saved = signature(data.files)
      setSession(data)
      if (!data.unlocked_task_ids.includes(ref.current.activeTask)) {
        ref.current.activeTask = data.active_task_id
        setActiveTask(data.active_task_id)
      }
      if (replaceFiles) {
        ref.current.files = data.files
        ref.current.activeFile = data.active_file_path
        ref.current.activeTask = data.active_task_id
        setFiles(data.files)
        setActiveFile(data.active_file_path)
        setActiveTask(data.active_task_id)
      }
      const clean = signature(ref.current.files) === ref.current.saved
      setSync(clean ? 'saved' : 'unsaved')
      if (clean) {
        try {
          localStorage.removeItem(key)
        } catch {
          /* Browser storage unavailable. */
        }
      } else remember()
    },
    [key, remember],
  )
  useEffect(() => {
    alive.current = true
    const controller = new AbortController()
    apiFetch<WorkspaceSessionResponse>(base, { signal: controller.signal })
      .then((data) => {
        if (!alive.current) return
        // Read before apply removes an acknowledged local draft.
        let recovered: WorkspaceFile[] | null = null
        try {
          const raw = JSON.parse(localStorage.getItem(key) || 'null')
          if (
            Array.isArray(raw?.files) &&
            raw.files.every(
              (f: WorkspaceFile) =>
                typeof f.path === 'string' && typeof f.content === 'string',
            ) &&
            signature(raw.files) !== signature(data.files)
          )
            recovered = raw.files
        } catch {
          /* Ignore malformed browser storage. */
        }
        ref.current.loaded = true
        apply(data, true)
        if (recovered) {
          setDraft(recovered)
          localStorage.setItem(
            key,
            JSON.stringify({ files: recovered, revision: data.revision }),
          )
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message)
      })
    return () => {
      alive.current = false
      streamController.current?.abort()
      controller.abort()
    }
  }, [base, key, apply])
  const enqueue = useCallback(<T>(operation: () => Promise<T>): Promise<T> => {
    const result = queue.current.catch(() => {}).then(operation)
    queue.current = result
    return result
  }, [])
  const saveCurrent = useCallback(async () => {
    if (!ref.current.loaded) throw new Error('Workspace is still loading.')
    if (ref.current.conflict)
      throw new Error('Resolve the workspace conflict before saving.')
    const snapshot = { ...ref.current, files: [...ref.current.files] }
    setSync('saving')
    try {
      const data = await apiFetch<WorkspaceSessionResponse>(`${base}/state`, {
        method: 'PUT',
        body: JSON.stringify({
          expected_revision: snapshot.revision,
          files: snapshot.files,
          active_file_path: snapshot.activeFile,
          active_task_id: snapshot.activeTask,
        }),
      })
      apply(data)
      return data
    } catch (e) {
      if (alive.current) {
        remember()
        if (e instanceof ApiError && e.status === 409) {
          ref.current.conflict = true
          setSync('conflict')
        } else setSync('unsaved')
        setError(
          e instanceof Error ? e.message : 'Could not save your workspace.',
        )
      }
      throw e
    }
  }, [apply, base, remember])
  const save = useCallback(() => enqueue(saveCurrent), [enqueue, saveCurrent])
  useEffect(() => {
    if (
      sync !== 'unsaved' ||
      !ref.current.loaded ||
      ref.current.conflict ||
      draft
    )
      return
    const timer = window.setTimeout(() => {
      void save().catch(() => {})
    }, 800)
    return () => window.clearTimeout(timer)
  }, [files, activeFile, activeTask, sync, save, draft])
  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => {
      if (signature(ref.current.files) !== ref.current.saved) {
        remember()
        event.preventDefault()
      }
    }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [remember])
  const edit = (path: string, content: string) => {
    if (ref.current.mutating) return
    const next = ref.current.files.map((f) =>
      f.path === path && !f.read_only ? { ...f, content } : f,
    )
    if (signature(next) === signature(ref.current.files)) return
    ref.current.files = next
    setFiles(next)
    setSync(ref.current.conflict ? 'conflict' : 'unsaved')
    remember()
  }
  const selectFile = (path: string) => {
    ref.current.activeFile = path
    setActiveFile(path)
    if (!ref.current.conflict) setSync('unsaved')
  }
  const selectTask = (id: string) => {
    ref.current.activeTask = id
    setActiveTask(id)
    if (!ref.current.conflict) setSync('unsaved')
  }
  const mutate = useCallback(
    async (
      endpoint: string,
      method: string,
      body: Record<string, unknown> = {},
      replaceFiles = false,
    ) => {
      if (replaceFiles) {
        ref.current.mutationCount += 1
        ref.current.mutating = true
        setMutating(true)
      }
      try {
        return await enqueue(async () => {
          const saved = await saveCurrent()
          const url = `${base}${endpoint}${method === 'DELETE' ? `${endpoint.includes('?') ? '&' : '?'}expected_revision=${saved.revision}` : ''}`
          const data = await apiFetch<WorkspaceSessionResponse>(url, {
            method,
            ...(method !== 'DELETE'
              ? {
                  body: JSON.stringify({
                    ...body,
                    expected_revision: saved.revision,
                  }),
                }
              : {}),
          })
          apply(data, replaceFiles)
          return data
        })
      } catch (e) {
        setError(
          e instanceof Error
            ? e.message
            : 'The operation failed. Your files are preserved.',
        )
        throw e
      } finally {
        if (replaceFiles) {
          ref.current.mutationCount -= 1
          if (ref.current.mutationCount === 0) {
            ref.current.mutating = false
            if (alive.current) setMutating(false)
          }
        }
      }
    },
    [apply, base, enqueue, saveCurrent],
  )
  const streamMentor = useCallback(
    async (endpoint: '/chat' | '/nudge', body: Record<string, unknown>) => {
      return enqueue(async () => {
        const controller = new AbortController()
        streamController.current = controller
        try {
          const saved = await saveCurrent()
          const taskId = String(body.task_id)
          setStreamingReply({ taskId, text: '' })
          const result = await readMentorStream(
            `${base}${endpoint}/stream`,
            { ...body, expected_revision: saved.revision },
            controller.signal,
            (text) => {
              if (alive.current) setStreamingReply({ taskId, text })
            },
          )
          apply(result)
          return result
        } catch (error) {
          if (alive.current)
            setError(
              error instanceof Error
                ? error.message
                : 'The AI response was interrupted.',
            )
          throw error
        } finally {
          if (alive.current) setStreamingReply(null)
          if (streamController.current === controller)
            streamController.current = null
        }
      })
    },
    [enqueue, saveCurrent, base, apply],
  )
  const recover = () => {
    if (!draft) return
    ref.current.files = draft
    setFiles(draft)
    setDraft(null)
    setSync('unsaved')
    remember()
  }
  const discardDraft = () => {
    setDraft(null)
    localStorage.removeItem(key)
  }
  const download = async () => {
    await save()
    const blob = await (await apiRequest(`${base}/export`)).blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${projectId}.zip`
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const dirtyPaths = new Set(
    files
      .filter(
        (f) =>
          session?.files.find((s) => s.path === f.path)?.content !== f.content,
      )
      .map((f) => f.path),
  )
  return {
    streamMentor,
    streamingReply,
    session,
    files,
    activeFile,
    activeTask,
    sync,
    error,
    setError,
    mutating,
    draft,
    recover,
    discardDraft,
    edit,
    selectFile,
    selectTask,
    save,
    mutate,
    download,
    dirtyPaths,
    base,
  }
}
