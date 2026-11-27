import { readMentorResponse } from './stream-reader'
import { apiRequest } from './supabase'
import type { WorkspaceSessionResponse } from '../types/workspace'

export async function readMentorStream(
  endpoint: string,
  body: Record<string, unknown>,
  signal: AbortSignal,
  onText: (text: string) => void,
): Promise<WorkspaceSessionResponse> {
  const response = await apiRequest(endpoint, {
    method: 'POST',
    body: JSON.stringify(body),
    signal,
  })
  return readMentorResponse(response, onText)
}
