import copy
import json
from pathlib import Path


def serialize(messages, n_calls, cost, status, submission):
    """Return a detached, JSON-compatible evidence record, not a live list alias."""
    return {"trajectory_format": "nudge-mini-swe-lab-1", "messages": copy.deepcopy(messages),
        "info": {"api_calls": n_calls, "cost": cost, "exit_status": status, "submission": submission}}


def save(path, data):
    """Create parent directories and atomically replace a UTF-8 trajectory file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
