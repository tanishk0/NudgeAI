"""Stream actual model text; save a reply only after successful generation."""
import asyncio
import json
import logging
from contextlib import suppress
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.database import SessionLocal


def mentor_stream(operation, user_id, project_id, payload):
    async def events():
        queue = asyncio.Queue(maxsize=32)

        async def delta(text):
            await queue.put({'type': 'delta', 'text': text})

        async def produce():
            try:
                with SessionLocal() as db:
                    async with asyncio.timeout(120):
                        result = await operation(db, user_id, project_id, payload, on_delta=delta)
                    await queue.put({'type': 'done', 'session': result.model_dump(mode='json')})
            except HTTPException as exc:
                await queue.put({'type': 'error', 'message': str(exc.detail), 'status': exc.status_code})
            except Exception:
                logging.getLogger(__name__).exception('Mentor stream failed')
                await queue.put({'type': 'error', 'message': 'The AI response could not finish. No assistant reply was saved or hint unlocked. Please retry.'})

        task = asyncio.create_task(produce())
        try:
            yield json.dumps({'type': 'start'}) + '\n'
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=10)
                except TimeoutError:
                    yield json.dumps({'type': 'ping'}) + '\n'
                    continue
                yield json.dumps(item, ensure_ascii=False) + '\n'
                if item['type'] in {'done', 'error'}:
                    break
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(events(), media_type='application/x-ndjson',
        headers={'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no'})
