"""Phase 2: structured tool requests. Execute only inside an isolated runner."""
import json
from copy import deepcopy
from phase_shell import execute, normalize_result


def bash_schema():
    return {"type": "function", "function": {"name": "bash", "description": "Run one Bash command in the isolated repository", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"], "additionalProperties": False}}}


def parse_tool(call):
    try:
        arguments = json.loads(call["function"]["arguments"])
        if call.get("type") != "function" or call["function"]["name"] != "bash":
            raise ValueError("Unknown tool")
        if not isinstance(call["id"], str) or not call["id"]:
            raise ValueError("Missing call id")
        if not isinstance(arguments, dict) or set(arguments) != {"command"}:
            raise ValueError("Expected only command")
        if not isinstance(arguments["command"], str) or not arguments["command"].strip():
            raise ValueError("Empty command")
        return arguments["command"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed tool request") from exc


def request_action(model, messages):
    return model.query(messages, tools=[bash_schema()])


def tool_turn(model, messages, cwd, runner=execute):
    reply = request_action(model, messages)
    calls = reply.get("tool_calls") or []
    # Validate the entire batch before any side effect.
    commands = [parse_tool(call) for call in calls]
    if len({call["id"] for call in calls}) != len(calls):
        raise ValueError("Duplicate tool call id")
    messages.append(deepcopy(reply))
    for call, command in zip(calls, commands):
        result = normalize_result(runner(command, cwd, timeout=2))
        messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
    return reply
