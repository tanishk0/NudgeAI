import { useState } from 'react'
import {
  Braces,
  Check,
  ChevronDown,
  ChevronRight,
  Code2,
  FileCode2,
  FilePlus2,
  FileText,
  Folder,
  FolderOpen,
  LockKeyhole,
  Pencil,
  Trash2,
  X,
} from 'lucide-react'
import type { WorkspaceFile } from '../../types/workspace'

export function getFileIcon(path: string) {
  const ext = path.split('.').pop()
  if (ext === 'py') return <FileCode2 size={15} className="file-python" />
  if (ext === 'json') return <Braces size={15} className="file-json" />
  if (['html', 'css', 'js', 'ts', 'tsx', 'jsx'].includes(ext || ''))
    return <Code2 size={15} className="file-code" />
  return <FileText size={15} className="file-other" />
}
interface Props {
  projectId: string
  files: WorkspaceFile[]
  activeFilePath: string
  dirtyPaths: Set<string>
  taskFilePaths?: string[]
  onSelectFile: (path: string) => void
  onCreateFile: (path: string) => Promise<void>
  onRenameFile: (oldPath: string, newPath: string) => Promise<void>
  onDeleteFile: (path: string) => Promise<void>
}
interface Node {
  name: string
  path: string
  file?: WorkspaceFile
  children: Map<string, Node>
}
export function FileExplorer({
  projectId,
  files,
  activeFilePath,
  dirtyPaths,
  taskFilePaths = [],
  onSelectFile,
  onCreateFile,
  onRenameFile,
  onDeleteFile,
}: Props) {
  const [closed, setClosed] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState<{
    path?: string
    value: string
  } | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const root: Node = { name: projectId, path: '', children: new Map() }
  for (const file of files) {
    let parent = root
    file.path.split('/').forEach((name, index, segments) => {
      const path = segments.slice(0, index + 1).join('/')
      if (!parent.children.has(name))
        parent.children.set(name, { name, path, children: new Map() })
      parent = parent.children.get(name)!
      if (index === segments.length - 1) parent.file = file
    })
  }
  const toggle = (path: string) =>
    setClosed((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  const commit = async () => {
    if (!editing?.value.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      if (editing.path) await onRenameFile(editing.path, editing.value.trim())
      else await onCreateFile(editing.value.trim())
      setEditing(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update file.')
    } finally {
      setBusy(false)
    }
  }
  const render = (node: Node, depth: number) => {
    const folder = !node.file
    const open = !closed.has(node.path)
    return (
      <div key={node.path}>
        <div
          className={`tree-row ${node.path === activeFilePath ? 'selected' : ''} ${taskFilePaths.includes(node.path) ? 'task-related' : ''}`}
          style={{ paddingLeft: 12 + depth * 13 }}
        >
          <button
            className="tree-label"
            onClick={() =>
              folder ? toggle(node.path) : onSelectFile(node.path)
            }
            aria-expanded={folder ? open : undefined}
            title={
              taskFilePaths.includes(node.path)
                ? `${node.path} — used in this task`
                : node.path
            }
          >
            {folder ? (
              <>
                {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                {open ? <FolderOpen size={15} /> : <Folder size={15} />}
              </>
            ) : (
              <>
                <span className="tree-indent" />
                {getFileIcon(node.path)}
              </>
            )}
            <span>{node.name}</span>
            {taskFilePaths.includes(node.path) && (
              <span className="task-file-dot" aria-label="Used in this task" />
            )}
            {node.file?.read_only && <LockKeyhole size={11} />}
            {dirtyPaths.has(node.path) && <i className="dirty-dot" />}
          </button>
          {node.file && !node.file.is_starter && (
            <div className="tree-actions">
              <button
                aria-label={`Rename ${node.path}`}
                title="Rename file"
                onClick={() =>
                  setEditing({ path: node.path, value: node.path })
                }
              >
                <Pencil size={12} />
              </button>
              <button
                aria-label={`Delete ${node.path}`}
                title="Delete file"
                onClick={() => setDeleting(node.path)}
              >
                <Trash2 size={12} />
              </button>
            </div>
          )}
        </div>
        {deleting === node.path && (
          <div className="tree-confirm">
            <span>Delete this file?</span>
            <button
              disabled={busy}
              onClick={async () => {
                setBusy(true)
                try {
                  await onDeleteFile(node.path)
                  setDeleting(null)
                } catch (e) {
                  setError(
                    e instanceof Error ? e.message : 'Could not delete file.',
                  )
                } finally {
                  setBusy(false)
                }
              }}
            >
              Delete
            </button>
            <button onClick={() => setDeleting(null)}>Cancel</button>
          </div>
        )}
        {folder &&
          open &&
          [...node.children.values()]
            .sort(
              (a, b) =>
                Number(!!a.file) - Number(!!b.file) ||
                a.name.localeCompare(b.name),
            )
            .map((child) => render(child, depth + 1))}
      </div>
    )
  }
  return (
    <div className="file-tree">
      <div className="tree-root">
        <button onClick={() => toggle('')} aria-expanded={!closed.has('')}>
          {closed.has('') ? (
            <ChevronRight size={14} />
          ) : (
            <ChevronDown size={14} />
          )}
          <span>{projectId}</span>
        </button>
        <button
          aria-label="Create file"
          title="Create file"
          onClick={() => {
            setEditing({ value: '' })
            setError('')
          }}
        >
          <FilePlus2 size={15} />
        </button>
      </div>
      {editing && (
        <form
          className="file-edit-form"
          onSubmit={(e) => {
            e.preventDefault()
            void commit()
          }}
        >
          <label>
            {editing.path ? 'Rename file' : 'New file · folders/use/slashes.py'}
          </label>
          <div>
            <input
              autoFocus
              aria-label={editing.path ? 'New file path' : 'File path'}
              value={editing.value}
              disabled={busy}
              onChange={(e) =>
                setEditing({ ...editing, value: e.target.value })
              }
              onKeyDown={(e) => {
                if (e.key === 'Escape') setEditing(null)
              }}
              placeholder="src/example.py"
            />
            <button disabled={busy} aria-label="Save file path">
              <Check size={15} />
            </button>
            <button
              type="button"
              onClick={() => setEditing(null)}
              aria-label="Cancel file operation"
            >
              <X size={14} />
            </button>
          </div>
        </form>
      )}
      {error && (
        <p className="tree-error" role="alert">
          {error}
        </p>
      )}
      {!closed.has('') &&
        [...root.children.values()]
          .sort(
            (a, b) =>
              Number(!!a.file) - Number(!!b.file) ||
              a.name.localeCompare(b.name),
          )
          .map((node) => render(node, 0))}
      {!files.length && (
        <p className="tree-empty">No files match your search.</p>
      )}
    </div>
  )
}
