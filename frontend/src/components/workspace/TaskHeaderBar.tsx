import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Circle,
  FileCode2,
  ShieldAlert,
  Sparkles,
  XCircle,
} from 'lucide-react'
import type { TaskItem, TaskVerificationReport } from '../../types/workspace'

interface TaskHeaderBarProps {
  tasks: TaskItem[]
  activeTask: TaskItem
  completedTaskIds: string[]
  verification?: TaskVerificationReport
  aiFailureMode: string
  onSelectTask: (taskId: string) => void
  onSelectTargetFile: (filePath: string) => void
}

const CATEGORY_BADGES: Record<TaskItem['category'], string> = {
  security: 'border-[#f38ba8]/35 bg-[#f38ba8]/15 text-[#f38ba8]',
  architecture: 'border-[#cba6f7]/35 bg-[#cba6f7]/15 text-[#cba6f7]',
  debugging: 'border-[#fab387]/35 bg-[#fab387]/15 text-[#fab387]',
  performance: 'border-[#a6e3a1]/35 bg-[#a6e3a1]/15 text-[#a6e3a1]',
}

export function TaskHeaderBar({
  tasks,
  activeTask,
  completedTaskIds,
  verification,
  aiFailureMode,
  onSelectTask,
  onSelectTargetFile,
}: TaskHeaderBarProps) {
  const [specExpanded, setSpecExpanded] = useState(false)

  const isTaskCompleted = completedTaskIds.includes(activeTask.id)
  const passedCriteriaCount = verification?.criteria_results
    ? verification.criteria_results.filter((c) => c.passed).length
    : isTaskCompleted
      ? activeTask.validation_criteria.length
      : 0

  return (
    <div className="relative z-20 border-b border-white/[0.07] bg-[#12131d]">
      {/* Compact Single-Line Task Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-3.5 py-2">
        {/* Left: Task Switcher Pills + Category + Title & 1-Line Objective */}
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          {/* Task Number Selector Pills */}
          <div className="flex items-center gap-1 rounded-lg bg-[#0b0c10] p-0.5 border border-white/[0.06] shrink-0">
            {tasks.map((t) => {
              const done = completedTaskIds.includes(t.id)
              const selected = t.id === activeTask.id
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => onSelectTask(t.id)}
                  className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono text-[11px] font-medium transition-colors cursor-pointer ${
                    selected
                      ? 'bg-[#1f2335] text-white shadow-sm'
                      : 'text-white/50 hover:text-white/85'
                  }`}
                >
                  {done ? (
                    <CheckCircle2 className="h-3 w-3 text-[#a6e3a1]" />
                  ) : (
                    <span className="text-[10px] opacity-75">#{t.order}</span>
                  )}
                  <span>Task {t.order}</span>
                </button>
              )
            })}
          </div>

          {/* Category Badge */}
          <span
            className={`shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider ${
              CATEGORY_BADGES[activeTask.category]
            }`}
          >
            {activeTask.category}
          </span>

          {/* Task Title + 1-Line Description */}
          <div className="flex items-baseline gap-2 min-w-0 flex-1">
            <span className="font-sans text-xs font-semibold text-white shrink-0">
              {activeTask.title}
            </span>
            <span className="text-white/30 shrink-0">&mdash;</span>
            <p className="truncate text-xs text-white/60">
              {activeTask.objective}
            </p>
          </div>
        </div>

        {/* Right: Target File Pill + Expandable Spec Toggle */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => onSelectTargetFile(activeTask.target_file)}
            title="Jump to target file"
            className="hidden sm:inline-flex items-center gap-1 rounded-md border border-white/[0.07] bg-white/[0.03] px-2 py-1 font-mono text-[11px] text-[#7aa2f7] hover:bg-white/[0.07] transition-colors cursor-pointer"
          >
            <FileCode2 className="h-3 w-3" />
            <span>{activeTask.target_file}</span>
          </button>

          <button
            type="button"
            onClick={() => setSpecExpanded((prev) => !prev)}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-all cursor-pointer ${
              specExpanded
                ? 'border-[#7aa2f7]/50 bg-[#7aa2f7]/15 text-white'
                : 'border-white/[0.09] bg-[#181a28] text-white/85 hover:border-white/20 hover:text-white'
            }`}
          >
            <span>View Spec / Criteria</span>
            <span className="rounded bg-white/10 px-1.5 py-0.2 font-mono text-[10px] text-[#ffb86c]">
              {passedCriteriaCount}/{activeTask.validation_criteria.length}
            </span>
            {specExpanded ? (
              <ChevronUp className="h-3.5 w-3.5 text-white/60" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5 text-white/60" />
            )}
          </button>
        </div>
      </div>

      {/* Expandable Floating Overlay Card for Full Task Instructions & Criteria */}
      {specExpanded && (
        <div className="absolute left-3 right-3 top-full mt-1.5 z-30 max-h-[72vh] overflow-y-auto rounded-xl border border-white/15 bg-[#11121c]/95 p-5 shadow-[0_24px_60px_rgba(0,0,0,0.8)] backdrop-blur-xl">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Left 7 Cols: Task Instructions & AI Failure Context */}
            <div className="lg:col-span-7 space-y-4">
              <div>
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#7aa2f7]">
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>
                    Task {activeTask.order}: {activeTask.title}
                  </span>
                </div>
                <p className="mt-1 text-xs text-white/75">{activeTask.objective}</p>
              </div>

              <div className="rounded-lg border border-white/[0.07] bg-[#0b0c10]/80 p-3.5 text-xs leading-relaxed text-white/85 prose prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {activeTask.instructions}
                </ReactMarkdown>
              </div>

              <div className="rounded-lg border border-[#ffb86c]/20 bg-[#ffb86c]/[0.05] p-3">
                <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#ffb86c]">
                  <ShieldAlert className="h-3.5 w-3.5" />
                  <span>Why the AI Failed in Production</span>
                </div>
                <p className="mt-1 text-xs text-white/70 leading-relaxed">
                  {aiFailureMode}
                </p>
              </div>
            </div>

            {/* Right 5 Cols: Live Validation Criteria Checklist */}
            <div className="lg:col-span-5 flex flex-col justify-between rounded-lg border border-white/[0.08] bg-[#0b0c10]/90 p-4">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold uppercase tracking-wider text-white/70">
                    Validation Criteria
                  </span>
                  <span className="font-mono text-[11px] text-[#ffb86c]">
                    {passedCriteriaCount} of {activeTask.validation_criteria.length} passed
                  </span>
                </div>

                <ul className="space-y-2.5">
                  {activeTask.validation_criteria.map((criterion, idx) => {
                    const evalItem = verification?.criteria_results?.[idx]
                    const passed = evalItem ? evalItem.passed : isTaskCompleted
                    const hasRun = Boolean(verification) || isTaskCompleted

                    return (
                      <li
                        key={criterion}
                        className={`rounded-lg border p-2.5 text-xs transition-colors ${
                          !hasRun
                            ? 'border-white/[0.06] bg-white/[0.02] text-white/75'
                            : passed
                              ? 'border-[#a6e3a1]/30 bg-[#a6e3a1]/[0.06] text-white'
                              : 'border-[#f38ba8]/30 bg-[#f38ba8]/[0.06] text-white'
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          {!hasRun ? (
                            <Circle className="h-4 w-4 shrink-0 text-white/30 mt-0.5" />
                          ) : passed ? (
                            <CheckCircle2 className="h-4 w-4 shrink-0 text-[#a6e3a1] mt-0.5" />
                          ) : (
                            <XCircle className="h-4 w-4 shrink-0 text-[#f38ba8] mt-0.5" />
                          )}
                          <div className="min-w-0 flex-1">
                            <p className="font-medium leading-snug">{criterion}</p>
                            {evalItem?.reason && (
                              <p className="mt-1 text-[11px] text-white/60">
                                {evalItem.reason}
                              </p>
                            )}
                          </div>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              </div>

              <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between text-[11px] text-white/45">
                <span>Press Run &amp; Verify to evaluate criteria</span>
                <button
                  type="button"
                  onClick={() => setSpecExpanded(false)}
                  className="text-[#7aa2f7] hover:underline cursor-pointer"
                >
                  Close Spec
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

