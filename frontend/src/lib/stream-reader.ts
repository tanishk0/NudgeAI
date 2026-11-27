import type { WorkspaceSessionResponse } from '../types/workspace'

export async function readMentorResponse(
  response: Response,
  onText: (text: string) => void,
): Promise<WorkspaceSessionResponse> {
  const reader = response.body?.getReader()
  if (!reader) throw new Error('Could not open the AI response stream.')
  const decoder = new TextDecoder()
  let buffer = ''
  let text = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      let boundary: number
      while ((boundary = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, boundary).trim()
        buffer = buffer.slice(boundary + 1)
        if (!line) continue
        const event = JSON.parse(line)
        if (event.type === 'error') throw new Error(event.message)
        if (event.type === 'delta') {
          text += event.text
          onText(text)
        }
        if (event.type === 'done')
          return event.session as WorkspaceSessionResponse
      }
      if (done)
        throw new Error(
          'The response was interrupted. No complete AI reply was received. Please retry.',
        )
    }
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
