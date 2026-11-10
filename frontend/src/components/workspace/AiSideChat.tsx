import { useState, useRef, useEffect, type FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  FileCode2,
  Lightbulb,
  Send,
  Sparkles,
  Unlock,
  Bot,
  User,
  Layers,
} from 'lucide-react'
import type { ChatMessageItem, TaskItem } from '../../types/workspace'

interface AiSideChatProps {
  activeFilePath: string
  activeTask: TaskItem
  hintLevel: number
  messages: ChatMessageItem[]
  sendingChat: boolean
  requestingHint: boolean
  onSendMessage: (message: string) => Promise<void>
  onRequestHint: () => Promise<void>
}

const HINT_STAGE_LABELS: Record<number, { button: string; subtitle: string }> = {
  0: {
    button: 'Get Nudge (Hint 1/3)',
    subtitle: 'Conceptual nudge based on your code diff',
  },
  1: {
    button: 'Get Nudge (Hint 2/3)',
    subtitle: 'Points to the exact function & stdlib primitive',
  },
  2: {
    button: 'Get Nudge (Hint 3/3)',
    subtitle: 'Structural blueprint without full spoiler',
  },
  3: {
    button: 'Reveal Solution (Step 4/4)',
    subtitle: 'Unlocks the complete annotated code fix',
  },
  4: {
    button: 'Solution Revealed (Re-send)',
    subtitle: 'All 3 hints & solution unlocked for this task',
  },
}

export function AiSideChat({
  activeFilePath,
  activeTask,
  hintLevel,
  messages,
  sendingChat,
  requestingHint,
  onSendMessage,
  onRequestHint,
}: AiSideChatProps) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, sendingChat, requestingHint])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || sendingChat) return
    setInput('')
    await onSendMessage(trimmed)
  }

  const stageInfo = HINT_STAGE_LABELS[Math.min(hintLevel, 4)]

  const getMessageBadge = (type: ChatMessageItem['message_type']) => {
    switch (type) {
      case 'hint_1':
        return {
          label: 'NUDGE 1/3 • CONCEPTUAL',
          style: 'border-[#ffb86c]/35 bg-[#ffb86c]/15 text-[#ffb86c]',
          card: 'border-[#ffb86c]/25 bg-[#ffb86c]/[0.05]',
        }
      case 'hint_2':
        return {
          label: 'NUDGE 2/3 • LOCALIZATION',
          style: 'border-[#fab387]/35 bg-[#fab387]/15 text-[#fab387]',
          card: 'border-[#fab387]/25 bg-[#fab387]/[0.05]',
        }
      case 'hint_3':
        return {
          label: 'NUDGE 3/3 • BLUEPRINT',
          style: 'border-[#cba6f7]/35 bg-[#cba6f7]/15 text-[#cba6f7]',
          card: 'border-[#cba6f7]/25 bg-[#cba6f7]/[0.05]',
        }
      case 'solution':
        return {
          label: 'STEP 4/4 • FULL SOLUTION',
          style: 'border-[#a6e3a1]/40 bg-[#a6e3a1]/15 text-[#a6e3a1]',
          card: 'border-[#a6e3a1]/30 bg-[#a6e3a1]/[0.05]',
        }
      default:
        return null
    }
  }

  return (
    <div className="flex h-full flex-col bg-[#11121a] text-[#cdd6f4]">
      {/* Top Chat Header */}
      <div className="flex h-9 items-center justify-between border-b border-white/[0.06] px-3.5 select-none">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-[#ffb86c]" />
          <span className="font-sans text-[11px] font-semibold uppercase tracking-[0.08em] text-white/85">
            Nudge AI Mentor
          </span>
        </div>
        <span className="rounded border border-[#7aa2f7]/25 bg-[#7aa2f7]/10 px-1.5 py-0.5 font-mono text-[10px] text-[#7aa2f7]">
          Context-Aware
        </span>
      </div>

      {/* Live Context & 4-Step Progressive Hint Meter */}
      <div className="border-b border-white/[0.06] bg-[#141622]/70 px-3.5 py-2.5 space-y-2">
        {/* Context Pills */}
        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
          <span className="text-white/40">Context:</span>
          <span className="inline-flex items-center gap-1 rounded bg-white/[0.05] border border-white/[0.07] px-1.5 py-0.5 font-mono text-[#7aa2f7]">
            <FileCode2 className="h-3 w-3" />
            @{activeFilePath}
          </span>
          <span className="inline-flex items-center gap-1 rounded bg-white/[0.05] border border-white/[0.07] px-1.5 py-0.5 font-mono text-[#cba6f7]">
            <Layers className="h-3 w-3" />
            Task #{activeTask.order}
          </span>
        </div>

        {/* 4-Step Progression Nodes (Hint 1 -> Hint 2 -> Hint 3 -> Solution) */}
        <div className="flex items-center justify-between gap-1.5 pt-0.5">
          {[
            { step: 1, label: 'Hint 1' },
            { step: 2, label: 'Hint 2' },
            { step: 3, label: 'Hint 3' },
            { step: 4, label: 'Solution' },
          ].map(({ step, label }) => {
            const unlocked = hintLevel >= step
            const isSolution = step === 4
            return (
              <div
                key={step}
                className={`flex-1 rounded-md border px-2 py-1 text-center font-mono text-[10px] transition-colors ${
                  unlocked
                    ? isSolution
                      ? 'border-[#a6e3a1]/40 bg-[#a6e3a1]/15 text-[#a6e3a1] font-semibold'
                      : 'border-[#ffb86c]/40 bg-[#ffb86c]/15 text-[#ffb86c] font-semibold'
                    : 'border-white/[0.06] bg-[#0b0c10]/60 text-white/35'
                }`}
              >
                {label}
              </div>
            )
          })}
        </div>
      </div>

      {/* Scrollable Chat & Hint Feed */}
      <div className="flex-1 overflow-y-auto px-3.5 py-4 space-y-4">
        {messages.map((msg) => {
          const isUser = msg.role === 'user'
          const badge = getMessageBadge(msg.message_type)

          return (
            <div
              key={msg.id}
              className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
            >
              {/* Role Header */}
              <div className="mb-1 flex items-center gap-1.5 text-[11px] text-white/45">
                {isUser ? (
                  <>
                    <span>You</span>
                    <User className="h-3 w-3 text-[#7aa2f7]" />
                  </>
                ) : (
                  <>
                    <Bot className="h-3.5 w-3.5 text-[#ffb86c]" />
                    <span className="font-medium text-white/70">Nudge AI</span>
                    {badge && (
                      <span
                        className={`rounded border px-1.5 py-0.2 font-mono text-[9px] font-semibold ${badge.style}`}
                      >
                        {badge.label}
                      </span>
                    )}
                  </>
                )}
              </div>

              {/* Message Bubble */}
              <div
                className={`max-w-[95%] rounded-xl border px-3.5 py-2.5 text-xs leading-relaxed ${
                  isUser
                    ? 'border-[#7aa2f7]/30 bg-[#1f2335] text-white'
                    : badge
                      ? `${badge.card} text-white/90`
                      : 'border-white/[0.07] bg-[#161824] text-white/85'
                }`}
              >
                <div className="prose prose-invert prose-xs max-w-none [&_pre]:rounded-lg [&_pre]:bg-[#0b0c10] [&_pre]:p-2.5 [&_pre]:border [&_pre]:border-white/10 [&_code]:font-mono [&_code]:text-[11px]">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          )
        })}

        {(sendingChat || requestingHint) && (
          <div className="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-[#161824] px-3.5 py-2.5 text-xs text-white/60">
            <span className="h-2 w-2 animate-ping rounded-full bg-[#ffb86c]" />
            <span>
              {requestingHint
                ? 'Analyzing your code diff to craft your next nudge...'
                : 'Nudge AI is thinking...'}
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Bottom Action & Chat Composer */}
      <div className="border-t border-white/[0.07] bg-[#0e0f17] p-3 space-y-2.5">
        {/* Progressive Nudge Trigger Button */}
        <button
          type="button"
          disabled={requestingHint || sendingChat}
          onClick={() => void onRequestHint()}
          className={`flex w-full items-center justify-between rounded-xl border px-3.5 py-2 text-left transition-all disabled:opacity-50 cursor-pointer ${
            hintLevel >= 3
              ? 'border-[#a6e3a1]/35 bg-[#a6e3a1]/10 hover:bg-[#a6e3a1]/20 text-[#a6e3a1]'
              : 'border-[#ffb86c]/35 bg-[#ffb86c]/10 hover:bg-[#ffb86c]/20 text-[#ffb86c]'
          }`}
        >
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-xs font-semibold">
              {hintLevel >= 3 ? (
                <Unlock className="h-3.5 w-3.5 shrink-0" />
              ) : (
                <Lightbulb className="h-3.5 w-3.5 shrink-0" />
              )}
              <span>{stageInfo.button}</span>
            </div>
            <p className="truncate text-[10px] text-white/60 mt-0.5">
              {stageInfo.subtitle}
            </p>
          </div>
          <span className="rounded-md bg-black/30 px-2 py-0.5 font-mono text-[10px]">
            {Math.min(hintLevel + 1, 4)}/4
          </span>
        </button>

        {/* Free-Form Question Composer */}
        <form onSubmit={handleSubmit} className="relative">
          <textarea
            rows={2}
            placeholder="Ask a conceptual question about this task or your code..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void handleSubmit(e)
              }
            }}
            className="w-full resize-none rounded-xl border border-white/[0.08] bg-[#14151f] py-2.5 pl-3 pr-10 text-xs text-white placeholder-white/35 focus:border-[#7aa2f7] focus:outline-none transition-colors"
          />
          <button
            type="submit"
            disabled={!input.trim() || sendingChat || requestingHint}
            className="absolute bottom-2.5 right-2.5 rounded-lg bg-[#7aa2f7] p-1.5 text-[#0b0c10] transition-opacity hover:opacity-90 disabled:opacity-30 cursor-pointer"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </form>
      </div>
    </div>
  )
}

