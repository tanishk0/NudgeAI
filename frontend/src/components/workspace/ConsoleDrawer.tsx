import {
  CheckCircle2,
  ChevronDown,
  Terminal,
  Trash2,
  XCircle,
  Clock,
  Sparkles,
} from 'lucide-react'
import type { TaskVerificationReport } from '../../types/workspace'

interface ConsoleDrawerProps {
  open: boolean
  running: boolean
  report?: TaskVerificationReport
  onToggle: () => void
  onClear: () => void
}

export function ConsoleDrawer({
  open,
  running,
  report,
  onToggle,
  onClear,
}: ConsoleDrawerProps) {
  if (!open) return null

  return (
    <div className="flex h-56 shrink-0 flex-col border-t border-white/[0.08] bg-[#0e0f17] text-[#cdd6f4]">
      {/* Console Tab Bar */}
      <div className="flex h-8 items-center justify-between border-b border-white/[0.06] bg-[#11121a] px-3 select-none">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 border-b-2 border-[#7aa2f7] py-1.5 text-[11px] font-semibold uppercase tracking-wider text-white">
            <Terminal className="h-3.5 w-3.5 text-[#7aa2f7]" />
            <span>Verification &amp; Test Output</span>
          </div>

          {report && !running && (
            <div className="flex items-center gap-2 text-xs">
              {report.passed_all ? (
                <span className="inline-flex items-center gap-1 rounded bg-[#a6e3a1]/15 px-2 py-0.5 font-mono text-[11px] font-medium text-[#a6e3a1]">
                  <CheckCircle2 className="h-3 w-3" />
                  All Checks Passed
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded bg-[#f38ba8]/15 px-2 py-0.5 font-mono text-[11px] font-medium text-[#f38ba8]">
                  <XCircle className="h-3 w-3" />
                  Checks Incomplete
                </span>
              )}
              <span className="inline-flex items-center gap-1 font-mono text-[11px] text-white/40">
                <Clock className="h-3 w-3" />
                {report.execution_ms}ms
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {report && (
            <button
              type="button"
              title="Clear console"
              onClick={onClear}
              className="rounded p-1 text-white/45 hover:bg-white/[0.08] hover:text-white transition-colors cursor-pointer"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            type="button"
            title="Minimize console"
            onClick={onToggle}
            className="rounded p-1 text-white/45 hover:bg-white/[0.08] hover:text-white transition-colors cursor-pointer"
          >
            <ChevronDown className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Console Body */}
      <div className="flex-1 overflow-y-auto p-3.5 font-mono text-xs leading-relaxed">
        {running ? (
          <div className="flex items-center gap-2.5 text-[#7aa2f7]">
            <span className="h-2 w-2 animate-ping rounded-full bg-[#7aa2f7]" />
            <span>
              Executing Python sandbox verification &amp; AI criteria evaluation...
            </span>
          </div>
        ) : !report ? (
          <div className="text-white/35">
            Click <span className="text-white/70">Run &amp; Verify (Ctrl+Enter)</span> in the top right to execute your code against the task validation suite.
          </div>
        ) : (
          <div className="space-y-3">
            {/* Per-Criterion Check Output */}
            <div className="space-y-1.5">
              {report.criteria_results.map((item) => (
                <div
                  key={item.criterion}
                  className="flex items-start gap-2 rounded-md bg-white/[0.02] px-2.5 py-1.5"
                >
                  {item.passed ? (
                    <span className="text-[#a6e3a1] font-bold">✓ PASS</span>
                  ) : (
                    <span className="text-[#f38ba8] font-bold">✗ FAIL</span>
                  )}
                  <div className="min-w-0 flex-1">
                    <span className="text-white/90">{item.criterion}</span>
                    {item.reason && (
                      <span className="ml-2 text-white/50">&mdash; {item.reason}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Architectural Feedback from AI Evaluator */}
            {report.architectural_feedback && (
              <div className="rounded-lg border border-[#cba6f7]/25 bg-[#cba6f7]/[0.06] px-3 py-2 text-xs text-white/85 font-sans">
                <span className="inline-flex items-center gap-1 font-semibold text-[#cba6f7] mr-1.5">
                  <Sparkles className="h-3 w-3" />
                  Evaluator Review:
                </span>
                {report.architectural_feedback}
              </div>
            )}

            {/* Raw Sandbox Output */}
            {report.sandbox_output && (
              <pre className="overflow-x-auto rounded-lg border border-white/[0.06] bg-[#090a0f] p-2.5 text-[11px] text-white/70 whitespace-pre-wrap">
                {report.sandbox_output}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

