import test from 'node:test'
import assert from 'node:assert/strict'
import { readMentorResponse } from '../src/lib/stream-reader.ts'

const encoder = new TextEncoder()
const events = (items) =>
  items.map((item) => JSON.stringify(item) + '\n').join('')

test('streams text before completion, including split UTF-8 and JSON chunks', async () => {
  let source
  const response = new Response(
    new ReadableStream({
      start(controller) {
        source = controller
      },
    }),
  )
  const received = []
  let firstChunk
  const first = new Promise((resolve) => {
    firstChunk = resolve
  })
  const result = readMentorResponse(response, (text) => {
    received.push(text)
    firstChunk()
  })
  const bytes = encoder.encode(events([{ type: 'delta', text: 'Hello 世界' }]))
  for (const byte of bytes) source.enqueue(Uint8Array.of(byte))
  await first // Must arrive while the connection is still open, before done.
  assert.deepEqual(received, ['Hello 世界'])
  source.enqueue(
    encoder.encode(
      events([
        { type: 'ping' },
        { type: 'delta', text: '!' },
        { type: 'done', session: { revision: 3 } },
      ]),
    ),
  )
  source.close()
  assert.equal((await result).revision, 3)
  assert.deepEqual(received, ['Hello 世界', 'Hello 世界!'])
})

test('partial output followed by an error is never accepted as complete', async () => {
  const response = new Response(
    events([
      { type: 'delta', text: 'Partial' },
      { type: 'error', message: 'Provider disconnected' },
    ]),
  )
  await assert.rejects(
    readMentorResponse(response, () => {}),
    /Provider disconnected/,
  )
})

test('a connection ending without done is reported as interrupted', async () => {
  const response = new Response(events([{ type: 'delta', text: 'Partial' }]))
  await assert.rejects(
    readMentorResponse(response, () => {}),
    /interrupted/,
  )
})
