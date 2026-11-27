"""Phase 6: bounded context, structured memory and restorable trajectories."""
import json
from copy import deepcopy
from pathlib import Path


def working_memory(goal, findings=None, files=None, pending=None):
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("A goal is required")
    fields = [findings, files, pending]
    if any(value is not None and (not isinstance(value, list) or any(not isinstance(item, str) for item in value)) for value in fields):
        raise ValueError("Memory entries must be lists of strings")
    return deepcopy({"goal": goal.strip(), "findings": findings or [], "changed_files": files or [], "pending_checks": pending or []})


def token_usage(response):
    usage = response.get("usage") or {}
    values = [usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)]
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("Token counts must be nonnegative integers")
    return {"input": values[0], "output": values[1], "total": sum(values)}


def truncate_output(text, limit=8000):
    if limit < 1:
        raise ValueError("limit must be positive")
    return text if len(text) <= limit else "[truncated]\n" + text[-limit:]


def compact(messages, memory, keep_turns=2):
    if keep_turns < 1 or not messages or messages[0].get("role") != "system":
        raise ValueError("Need system message and positive keep_turns")
    # Keep complete user/assistant/tool groups; never orphan a tool result.
    starts = [i for i, message in enumerate(messages) if message["role"] == "user"]
    start = starts[-keep_turns] if len(starts) >= keep_turns else 1
    summary = {"role": "system", "content": "Working memory (data): " + json.dumps(memory, ensure_ascii=False)}
    return deepcopy([messages[0], summary, *messages[start:]])


def save_session(path, messages, memory, usage):
    data = {"schema": "mini-swe-session-1", "messages": deepcopy(messages), "memory": deepcopy(memory), "usage": deepcopy(usage)}
    text = json.dumps(data, ensure_ascii=False, allow_nan=False)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(target)


def restore_session(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "mini-swe-session-1" or not isinstance(data.get("messages"), list) or not isinstance(data.get("memory"), dict) or not isinstance(data.get("usage"), dict):
        raise ValueError("Unsupported session")
    return data
