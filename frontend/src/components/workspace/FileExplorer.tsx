import { useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  FileCode2,
  FileJson,
  FileText,
  FolderOpen,
  Lock,
  Pencil,
  Plus,
  Trash2,
  Check,
  X,
} from 'lucide-react'
import type { WorkspaceFile } from '../../types/workspace'

interface FileExplorerProps {
  projectId: string
  files: WorkspaceFile[]
  activeFilePath: string
  dirtyPaths: Set<string>
  onSelectFile: (path: string) => void
  onCreateFile: (path: string) => Promise<void>
  onRenameFile: (oldPath: string, newPath: string) => Promise<void>
  onDeleteFile: (path: string) => Promise<void>
}

export function getFileIcon(path: string) {
  const lower = path.toLowerCase()
  if (lower.endsWith('.py')) {
    return <FileCode2 className="h-4 w-4 shrink-0 text-[#7aa2f7]" />
  }
  if (lower.endsWith('.md')) {
    return <FileText className="h-4 w-4 shrink-0 text-[#cba6f7]" />
  }
  if (lower.endsWith('.json')) {
    return <FileJson className="h-4 w-4 shrink-0 text-[#f9e2af]" />
  }
  return <FileCode2 className="h-4 w-4 shrink-0 text-[#89dceb]" />
}

export function FileExplorer({
  projectId,
  files,
  activeFilePath,
  dirtyPaths,
  onSelectFile,
  onCreateFile,
  onRenameFile,
  onDeleteFile,
}: FileExplorerProps) {
  const [folderOpen, setFolderOpen] = useState(true)
  const [creating, setCreating] = useState(false)
  const [newFileName, setNewFileName] = useState('')
  const [renamingPath, setRenamingPath] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [opError, setOpError] = useState<string | null>(null)

  const handleConfirmCreate = async () => {
    const trimmed = newFileName.trim()
    if (!trimmed) {
      setCreating(false)
      return
    }
    setOpError(null)
    try {
      await onCreateFile(trimmed)
      setNewFileName('')
      setCreating(false)
    } catch (err) {
      setOpError(err instanceof Error ? err.message : 'Could not create file')
    }
  }

  const handleConfirmRename = async (oldPath: string) => {
    const trimmed = renameValue.trim()
    if (!trimmed || trimmed === oldPath) {
      setRenamingPath(null)
      return
    }
    setOpError(null)
    try {
      await onRenameFile(oldPath, trimmed)
      setRenamingPath(null)
    } catch (err) {
      setOpError(err instanceof Error ? err.message : 'Could not rename file')
    }
  }

  return (
    <div className="flex h-full flex-col bg-[#11121a] text-[#cdd6f4] select-none">
      {/* Explorer Header */}
      <div className="flex h-9 items-center justify-between border-b border-white/[0.06] px-3">
        <span className="font-sans text-[11px] font-semibold uppercase tracking-[0.08em] text-white/50">
          Explorer
        </span>
        <button
          type="button"
          title="New File"
          onClick={() => {
            setFolderOpen(true)
            setCreating(true)
            setNewFileName('')
            setOpError(null)
          }}
          className="rounded p-1 text-white/55 hover:bg-white/[0.08] hover:text-white transition-colors cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>

      {opError && (
        <div className="mx-2 mt-2 flex items-center justify-between rounded-lg border border-[#f38ba8]/30 bg-[#f38ba8]/10 px-2.5 py-1.5 text-[11px] text-[#f38ba8]">
          <span className="truncate">{opError}</span>
          <button
            type="button"
            onClick={() => setOpError(null)}
            className="ml-1 text-white/60 hover:text-white cursor-pointer"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* Project Root Folder */}
      <div className="flex-1 overflow-y-auto py-1.5">
        <button
          type="button"
          onClick={() => setFolderOpen((prev) => !prev)}
          className="flex w-full items-center gap-1.5 px-2.5 py-1 text-left text-xs font-semibold text-white/80 hover:bg-white/[0.04] cursor-pointer"
        >
          {folderOpen ? (
            <ChevronDown className="h-3.5 w-3.5 text-white/50" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-white/50" />
          )}
          <FolderOpen className="h-3.5 w-3.5 text-[#ffb86c]" />
          <span className="truncate font-mono text-[11px] uppercase tracking-wider">
            {projectId}
          </span>
        </button>

        {folderOpen && (
          <div className="mt-0.5 space-y-0.5">
            {files.map((file) => {
              const isActive = file.path === activeFilePath
              const isDirty = dirtyPaths.has(file.path)
              const isRenaming = renamingPath === file.path

              if (isRenaming) {
                return (
                  <div
                    key={file.path}
                    className="flex items-center gap-1 px-4 py-1 bg-[#1f2335]"
                  >
                    <input
                      type="text"
                      autoFocus
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') void handleConfirmRename(file.path)
                        if (e.key === 'Escape') setRenamingPath(null)
                      }}
                      className="w-full rounded border border-[#7aa2f7] bg-[#0b0c10] px-1.5 py-0.5 font-mono text-xs text-white focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => void handleConfirmRename(file.path)}
                      className="text-[#a6e3a1] hover:text-white cursor-pointer"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setRenamingPath(null)}
                      className="text-white/50 hover:text-white cursor-pointer"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )
              }

              return (
                <div
                  key={file.path}
                  onClick={() => onSelectFile(file.path)}
                  className={`group flex items-center justify-between pl-6 pr-2.5 py-1.5 text-xs transition-colors cursor-pointer ${
                    isActive
                      ? 'bg-[#1f2335] text-white border-l-2 border-[#7aa2f7]'
                      : 'text-white/70 hover:bg-white/[0.04] hover:text-white border-l-2 border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {getFileIcon(file.path)}
                    <span className="truncate font-mono text-[12px]">
                      {file.path}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    {isDirty && (
                      <span
                        title="Modified"
                        className="h-2 w-2 rounded-full bg-[#ffb86c]"
                      />
                    )}
                    {file.read_only && (
                      <span
                        title="Read-only reference file"
                        className="text-white/40"
                      >
                        <Lock className="h-3 w-3" />
                      </span>
                    )}
                    {!file.is_starter && (
                      <div className="hidden group-hover:flex items-center gap-1">
                        <button
                          type="button"
                          title="Rename file"
                          onClick={(e) => {
                            e.stopPropagation()
                            setRenamingPath(file.path)
                            setRenameValue(file.path)
                          }}
                          className="rounded p-0.5 text-white/50 hover:bg-white/10 hover:text-white cursor-pointer"
                        >
                          <Pencil className="h-3 w-3" />
                        </button>
                        <button
                          type="button"
                          title="Delete file"
                          onClick={(e) => {
                            e.stopPropagation()
                            void onDeleteFile(file.path)
                          }}
                          className="rounded p-0.5 text-white/50 hover:bg-[#f38ba8]/20 hover:text-[#f38ba8] cursor-pointer"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}

            {/* Inline New File Input */}
            {creating && (
              <div className="flex items-center gap-1.5 pl-6 pr-2.5 py-1 bg-[#1f2335]/70">
                <FileCode2 className="h-4 w-4 shrink-0 text-[#7aa2f7]" />
                <input
                  type="text"
                  autoFocus
                  placeholder="helper.py"
                  value={newFileName}
                  onChange={(e) => setNewFileName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void handleConfirmCreate()
                    if (e.key === 'Escape') setCreating(false)
                  }}
                  className="w-full rounded border border-[#7aa2f7] bg-[#0b0c10] px-1.5 py-0.5 font-mono text-xs text-white placeholder-white/30 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => void handleConfirmCreate()}
                  className="text-[#a6e3a1] hover:text-white cursor-pointer"
                >
                  <Check className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setCreating(false)}
                  className="text-white/50 hover:text-white cursor-pointer"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Subtle Footer Legend */}
      <div className="border-t border-white/[0.06] px-3 py-2 text-[11px] text-white/40 flex items-center justify-between">
        <span>{files.length} files in workspace</span>
        <span className="font-mono text-[10px] text-white/30">JSONB synced</span>
      </div>
    </div>
  )
}

