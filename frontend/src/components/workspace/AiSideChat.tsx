import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  Bot,
  FileCode2,
  Lightbulb,
  Loader2,
  Send,
  Sparkles,
} from 'lucide-react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessageItem, TaskItem } from '../../types/workspace'

interface Props {
  activeFilePath: string
  activeTask: TaskItem
  hintLevel: number
  messages: ChatMessageItem[]
  sendingChat: boolean
  requestingHint: boolean
  streamingText: string
  onSendMessage: (message: string) => Promise<void>
  onRequestHint: () => Promise<void>
  onRevealCode: (path: string, line: number) => void
}
export function AiSideChat({
  activeFilePath,
  activeTask,
  hintLevel,
  messages,
  sendingChat,
  requestingHint,
  streamingText,
  onSendMessage,
  onRequestHint,
  onRevealCode,
}: Props) {
  const markdownComponents: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith('#code?')) {
        const params = new URLSearchParams(href.slice(6))
        const path = params.get('path')
        const line = Number(params.get('line'))
        if (path && Number.isInteger(line) && line > 0)
          return (
            <button
              className="mentor-code-link"
              onClick={() => onRevealCode(path, line)}
            >
              {children}
            </button>
          )
        return <span>{children}</span>
      }
      return (
        <a href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      )
    },
  }
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const bottom = useRef<HTMLDivElement>(null)
  const busy = sendingChat || requestingHint
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [messages.length, busy, streamingText])
  const send = async (event: FormEvent) => {
    event.preventDefault()
    const question = input.trim()
    if (!question || busy) return
    setError('')
    try {
      await onSendMessage(question)
      setInput((current) => (current.trim() === question ? '' : current))
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Could not send your question. Please retry.',
      )
    }
  }
  return (
    <div className="mentor-chat">
      <div className="chat-section-title">
        <Sparkles size={14} />
        <span>AI MENTOR</span>
        <span className="mentor-context-label">Task context attached</span>
      </div>
      <div
        className="chat-feed"
        aria-live="polite"
        aria-relevant="additions text"
      >
        {messages.length ? (
          messages.map((message) => (
            <article
              key={message.id}
              className={`chat-message ${message.role}`}
            >
              <div className="chat-message-author">
                {message.role === 'assistant' ? (
                  <>
                    <span className="bot-avatar">
                      <Sparkles size={13} />
                    </span>
                    <strong>Nudge</strong>
                    {message.message_type.startsWith('hint') && (
                      <small>Hint {message.message_type.split('_')[1]}</small>
                    )}
                    {message.message_type === 'solution' && (
                      <small>Solution</small>
                    )}
                  </>
                ) : (
                  <>
                    <span className="user-avatar">Y</span>
                    <strong>You</strong>
                  </>
                )}
              </div>
              <div className="markdown-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            </article>
          ))
        ) : !busy ? (
          <div className="chat-welcome">
            <Bot size={27} />
            <h3>Let’s work through it.</h3>
            <p>
              Ask about a function, explore a concept, or get a nudge on{' '}
              <strong>{activeTask.title}</strong>.
            </p>
            <button
              onClick={() =>
                setInput('Help me understand where to start with this task.')
              }
            >
              <Lightbulb size={14} />
              Help me get started
            </button>
          </div>
        ) : null}
        {streamingText && (
          <article className="chat-message assistant">
            <div className="chat-message-author">
              <strong>Nudge</strong>
              <small>Writing…</small>
            </div>
            <div className="markdown-content">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {streamingText}
              </ReactMarkdown>
            </div>
          </article>
        )}
        {busy && !streamingText && (
          <div className="mentor-thinking">
            <Loader2 size={14} className="spin" />
            {requestingHint
              ? 'Preparing your next nudge…'
              : 'Reading your code…'}
          </div>
        )}
        <div ref={bottom} />
      </div>
      <div className="chat-composer">
        <button
          className="nudge-button"
          disabled={busy}
          onClick={() => {
            setError('')
            void onRequestHint().catch((e) => setError(e.message))
          }}
        >
          <Lightbulb size={15} />
          <span>
            {hintLevel < 3
              ? 'Give me a nudge'
              : hintLevel === 3
                ? 'Reveal solution'
                : 'Review solution'}
          </span>
          <small>{Math.min(hintLevel + 1, 4)}/4</small>
        </button>
        {error && (
          <p className="chat-error" role="alert">
            {error}
          </p>
        )}
        <form onSubmit={(event) => void send(event)}>
          <label className="composer-context">
            <FileCode2 size={12} />
            {activeFilePath}
            <span>attached</span>
          </label>
          <textarea
            aria-label="Ask your AI mentor"
            maxLength={6000}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your code…"
            rows={3}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void send(event)
              }
            }}
          />
          <div className="composer-footer">
            <span>Enter to send · Shift + Enter for a new line</span>
            <button
              aria-label="Send message"
              type="submit"
              disabled={busy || !input.trim()}
            >
              <Send size={14} />
            </button>
          </div>
        </form>
        <p className="mentor-footnote">
          Hints guide your thinking. You build the solution.
        </p>
      </div>
    </div>
  )
}
