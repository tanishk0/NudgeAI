"""Bounded per-user limits for the single-worker college deployment."""
from collections import deque
import threading
import time
from fastapi import HTTPException

_requests = {}
_lock = threading.Lock()

def enforce(user_id, path):
    kind = path.rsplit("/", 1)[-1]
    limit = 12 if kind in {"run", "verify"} else 30 if kind in {"chat", "nudge"} else 180
    group = "execution" if kind in {"run", "verify"} else "ai" if kind in {"chat", "nudge"} else "general"
    now = time.monotonic()
    with _lock:
        if len(_requests) > 4096:
            for key in list(_requests):
                if not _requests[key] or _requests[key][-1] < now-60:
                    del _requests[key]
        key=(user_id,group)
        history=_requests.setdefault(key,deque())
        while history and history[0] < now-60:
            history.popleft()
        if len(history) >= limit:
            raise HTTPException(429,"You’re moving quickly. Please wait a minute before trying again.",headers={"Retry-After":"60"})
        history.append(now)
