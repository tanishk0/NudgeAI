"""Trusted capstone checks. Provider and Docker calls never reach external services."""
import importlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def raises(kind, operation):
    try:
        operation()
    except kind:
        return
    raise AssertionError(f"Expected {kind.__name__}")


def tool(command="pwd", ident="call_1"):
    return {"id": ident, "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": command})}}


def ok(output="done", code=0, timed_out=False):
    return {"output": output, "returncode": code, "timed_out": timed_out}


class ModelDouble:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def query(self, messages, tools=None):
        self.calls.append((json.loads(json.dumps(messages)), tools))
        return self.replies.pop(0)


def check(key, case, directory):
    module = importlib.import_module("phase_" + key)
    if key == "core":
        calls = []
        def complete(**kwargs):
            calls.append(kwargs)
            return {"choices": [{"message": {"role": "assistant", "content": "reply"}}]}
        model = module.Model("test/model", complete=complete)
        if case == 0:
            messages = [{"role": "user", "content": "hi"}]
            schemas = [{"type": "function"}]
            reply = model.query(messages, tools=schemas)
            messages[0]["content"] = "changed"
            schemas[0]["type"] = "changed"
            require(calls[0]["model"] == "test/model" and calls[0]["messages"][0]["content"] == "hi" and calls[0]["tools"][0]["type"] == "function" and calls[0]["tool_choice"] == "auto", "Pass detached provider arguments")
            require(reply == {"role": "assistant", "content": "reply"}, "Normalize the provider envelope")
            boxed = module.Model("test/model", complete=lambda **kw: SimpleNamespace(model_dump=lambda: {"choices": [{"message": reply}]}))
            require(boxed.query([]) == reply, "Support provider model_dump responses")
        elif case == 1:
            agent = module.ConversationAgent(model)
            require(agent.chat("  first  ") == "reply" and agent.chat("second") == "reply", "Return reply content")
            require([m["role"] for m in agent.messages] == ["system", "user", "assistant", "user", "assistant"], "Keep ordered conversation")
            require(agent.messages[1]["content"] == "first" and len(calls[1]["messages"]) == 4, "Include earlier conversation on next turn")
            require(len(module.ConversationAgent(model).messages) == 1, "Do not share state")
        else:
            for text in ["", "  ", None, 42]:
                raises(ValueError, lambda: module.Model(text, complete=complete))
                raises(ValueError, lambda: module.ConversationAgent(model).chat(text))
            require(module.ConversationAgent(model).run(["one", "two"]) == ["reply", "reply"], "Run all input turns")
    elif key == "tools":
        if case == 0:
            schema = module.bash_schema()
            require(schema["type"] == "function" and schema["function"]["name"] == "bash", "Define a Bash function tool")
            params = schema["function"]["parameters"]
            require(params["required"] == ["command"] and params["properties"]["command"]["type"] == "string" and params["additionalProperties"] is False, "Require one command string")
            require(module.parse_tool(tool("printf hi")) == "printf hi", "Decode command JSON")
            for args in ["[]", "null", "{", '{"command": 4}', '{"command": " "}', '{"command":"pwd","other":1}']:
                call = tool(); call["function"]["arguments"] = args
                raises(ValueError, lambda: module.parse_tool(call))
            for call in [{}, dict(tool(), id=""), dict(tool(), type="other")]:
                raises(ValueError, lambda: module.parse_tool(call))
            call = tool(); call["function"]["name"] = "unknown"
            raises(ValueError, lambda: module.parse_tool(call))
        elif case == 1:
            calls = []
            def runner(command, cwd, timeout):
                calls.append((command, cwd, timeout))
                return ok("failure detail", 7)
            model = ModelDouble([{"role": "assistant", "content": None, "tool_calls": [tool()]}])
            messages = [{"role": "user", "content": "inspect"}]
            module.tool_turn(model, messages, directory, runner)
            require(calls == [("pwd", directory, 2)] and model.calls[0][1][0]["function"]["name"] == "bash", "Bind and execute exactly once")
            require(messages[-1]["role"] == "tool" and messages[-1]["tool_call_id"] == "call_1" and json.loads(messages[-1]["content"]) == ok("failure detail", 7), "Return result tied to request")
        else:
            for batch in [[tool(), {"id": "bad"}], [tool(), tool()]]:
                calls, messages = [], [{"role": "user", "content": "inspect"}]
                before = json.dumps(messages)
                model = ModelDouble([{"role": "assistant", "tool_calls": batch}])
                raises(ValueError, lambda: module.tool_turn(model, messages, directory, lambda *a, **k: calls.append(a)))
                require(not calls and json.dumps(messages) == before, "Reject the entire batch before side effects")
    elif key == "autonomy":
        if case == 0:
            messages = module.task_messages("  repair addition  ", directory)
            require([m["role"] for m in messages] == ["system", "user"] and "repair addition" in messages[1]["content"] and directory in messages[1]["content"], "Fill the task template")
            system = messages[0]["content"].lower()
            require("test" in system and "untrusted" in system and "inspect" in system, "Require exploration, testing, and a trust boundary")
            raises(ValueError, lambda: module.task_messages(" ", directory))
        elif case == 1:
            # The commands and tests are real; only model decisions are prepared.
            fixture = Path(directory) / "repo"
            shutil.copytree(Path(__file__).parent / "buggy_repository", fixture)
            from environment import execute
            initial = execute("python -m unittest discover -s . -p 'test_*.py'", str(fixture), timeout=2)
            require(initial["returncode"] != 0, "Fixture begins with failing tests")
            repair = "python -c \"from pathlib import Path; p=Path('calculator.py'); p.write_text(p.read_text().replace('a - b', 'a + b'))\""
            model = ModelDouble([
                {"role": "assistant", "tool_calls": [tool("ls; cat calculator.py", "read")]},
                {"role": "assistant", "tool_calls": [tool(repair, "edit")]},
                {"role": "assistant", "content": "Repaired addition and checked it."},
            ])
            result = module.run_agent(model, "Fix add", str(fixture), execute)
            require(result["status"] == "Submitted" and result["verified"] is True and "a + b" in (fixture / "calculator.py").read_text(), "Repair and independently verify")
            require(result["tests"]["returncode"] == 0 and len(model.calls) == 3, "Preserve final test evidence")
        else:
            model = ModelDouble([{"role": "assistant", "content": "Fixed"}])
            result = module.run_agent(model, "Fix bug", directory, lambda *a, **k: ok("failed", 1))
            require(result["verified"] is False, "A claim cannot override failed tests")
            model = ModelDouble([{"role": "assistant", "tool_calls": [tool()]}] * 2)
            result = module.run_agent(model, "Fix bug", directory, lambda *a, **k: ok(), max_steps=2)
            require(result["status"] == "LimitsExceeded" and len(model.calls) == 2, "Stop exactly at the step budget")
            raises(ValueError, lambda: module.run_agent(model, "task", directory, lambda *a, **k: ok(), max_steps=0))
    elif key == "docker":
        calls = []
        def cli(args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(stdout="container-or-output", stderr="", returncode=0)
        env = module.DockerEnvironment(cli=cli)
        if case == 0:
            require(env.name != module.DockerEnvironment(cli=cli).name, "Use unique container names")
            env.start(directory)
            args, kwargs = calls[0]
            require(args[:3] == ["docker", "run", "-d"] and kwargs["check"] is True and kwargs["timeout"] > 0, "Start a checked detached container")
            for flag, value in [("--network", "none"), ("--cap-drop", "ALL"), ("--security-opt", "no-new-privileges"), ("--user", "1000:1000"), ("--memory", "256m"), ("--cpus", "1"), ("--pids-limit", "64"), ("--workdir", "/work")]:
                require(args[args.index(flag) + 1] == value, "Enforce " + flag)
            require("--read-only" in args and any("target=/input,readonly" in a for a in args) and args.count("--tmpfs") == 2, "Constrain writable storage")
            require(calls[1][0][:3] == ["docker", "exec", env.name] and "cp -R /input/. /work/" in calls[1][0] and env.started, "Provision before returning")
        elif case == 1:
            raises(RuntimeError, lambda: env.execute("pwd"))
            env.start(directory)
            env.cli = lambda args, **kwargs: (calls.append((args, kwargs)) or SimpleNamespace(stdout="x" * 10000, stderr="error", returncode=7))
            result = env.execute("pwd")
            require(result["returncode"] == 7 and result["output"].endswith("error") and len(result["output"]) == 8000 and not result["timed_out"], "Keep bounded output and failure status")
            require(calls[-1][0] == ["docker", "exec", env.name, "/bin/bash", "-lc", "pwd"], "Execute inside named container")
        else:
            env.start(directory)
            def timeout_cli(args, **kwargs):
                calls.append((args, kwargs))
                if args[1] == "exec":
                    raise subprocess.TimeoutExpired(args, .01, output=b"partial")
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            env.cli = timeout_cli
            result = env.execute("sleep 9", timeout=.01)
            require(result["timed_out"] and result["returncode"] != 0 and "partial" in result["output"] and not env.started, "Timeout stops environment and keeps output")
            require(calls[-1][0] == ["docker", "rm", "-f", env.name], "Remove timed-out container")
            calls.clear()
            def broken_cli(args, **kwargs):
                calls.append((args, kwargs))
                if args[1] == "exec":
                    raise RuntimeError("copy failed")
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            env = module.DockerEnvironment(cli=broken_cli)
            raises(RuntimeError, lambda: env.start(directory))
            require(not env.started and calls[-1][0][1:3] == ["rm", "-f"], "Clean partial initialization")
    elif key == "reliability":
        if case == 0:
            attempts, waits = [], []
            def flaky():
                attempts.append(1)
                if len(attempts) < 3:
                    raise module.TransientAPIError("temporarily unavailable")
                return "ready"
            require(module.retry_api(flaky, sleep=waits.append) == "ready" and len(attempts) == 3 and waits == [1, 2], "Retry with exponential waits")
            attempts.clear()
            def permanent():
                attempts.append(1)
                raise ValueError("invalid")
            raises(ValueError, lambda: module.retry_api(permanent, sleep=waits.append))
            require(len(attempts) == 1, "Permanent failures do not retry")
            attempts.clear()
            def unavailable():
                attempts.append(1)
                raise module.TransientAPIError("outage")
            raises(module.TransientAPIError, lambda: module.retry_api(unavailable, attempts=2, sleep=lambda t: None))
            require(len(attempts) == 2, "Stop after bounded attempts")
            raises(ValueError, lambda: module.retry_api(flaky, attempts=0))
        elif case == 1:
            usage = dict(steps=0, tokens=0, cost=0, seconds=0)
            limits = dict(steps=2, tokens=100, cost=.5, seconds=5)
            require(module.remaining_budget(usage, limits) is True, "Allow available budget")
            for key in limits:
                raises(module.LimitsExceeded, lambda: module.remaining_budget(dict(usage, **{key: limits[key]}), limits))
                for invalid in [float("nan"), float("inf"), True, -1, "0"]:
                    raises(ValueError, lambda: module.remaining_budget(dict(usage, **{key: invalid}), limits))
        else:
            calls = []
            raises(module.MalformedToolCall, lambda: module.safe_tool({}, directory, lambda *a, **k: calls.append(a)))
            require(not calls, "Malformed requests never reach runner")
            result = module.safe_tool(tool(), directory, lambda *a, **k: ok("partial", -1, True))
            require(result == ok("partial", -1, True), "Preserve timeout evidence")
    elif key == "memory":
        if case == 0:
            require(module.token_usage({"usage": {"prompt_tokens": 8, "completion_tokens": 3}}) == {"input": 8, "output": 3, "total": 11}, "Sum provider usage")
            require(module.token_usage({})["total"] == 0, "Default missing usage")
            for invalid in [-1, True, 1.5, "2"]:
                raises(ValueError, lambda: module.token_usage({"usage": {"prompt_tokens": invalid}}))
            require(module.truncate_output("123456", 3) == "[truncated]\n456" and module.truncate_output("123", 3) == "123", "Mark omitted output")
            raises(ValueError, lambda: module.truncate_output("x", 0))
        elif case == 1:
            messages = [{"role": "system", "content": "rules"}, {"role": "user", "content": "old"}, {"role": "assistant", "content": "old reply"}, {"role": "user", "content": "recent"}, {"role": "assistant", "tool_calls": [tool()]}, {"role": "tool", "tool_call_id": "call_1", "content": "result"}]
            memory = {"goal": "repair", "pending_checks": ["tests"]}
            result = module.compact(messages, memory, keep_turns=1)
            require(result[0] == messages[0] and result[1]["content"].startswith("Working memory (data): ") and "repair" in result[1]["content"] and result[2:] == messages[3:], "Keep complete recent exchanges and memory")
            result[-1]["content"] = "changed"
            require(messages[-1]["content"] == "result", "Do not alias live history")
            raises(ValueError, lambda: module.compact(messages, memory, 0))
        else:
            path = Path(directory) / "nested" / "session.json"
            module.save_session(path, [{"role": "user", "content": "नमस्ते"}], {"goal": "fix"}, {"tokens": 4})
            data = module.restore_session(path)
            require(data["messages"][0]["content"] == "नमस्ते" and data["usage"]["tokens"] == 4 and data["memory"]["goal"] == "fix", "Restore messages, memory and usage")
            before = path.read_text(encoding="utf-8")
            raises((TypeError, ValueError), lambda: module.save_session(path, [], {"bad": object()}, {}))
            require(path.read_text(encoding="utf-8") == before, "Preserve previous record on failure")
            path.write_text('{"schema":"unknown"}', encoding="utf-8")
            raises(ValueError, lambda: module.restore_session(path))
    elif key == "security":
        root = Path(directory)
        if case == 0:
            require(module.allowed_path(root, "src/example.py") == (root / "src/example.py").resolve(), "Resolve an allowed relative path")
            for path in ["../escape", str(root / "absolute"), ".env", ".env.local", ".git/config", ".aws/config", ".ssh/id_rsa"]:
                raises(PermissionError, lambda: module.allowed_path(root, path))
            outside = root.parent / (root.name + "-outside")
            link = root / "escape-link"
            link.symlink_to(outside, target_is_directory=True)
            raises(PermissionError, lambda: module.allowed_path(root, "escape-link/secret"))
        elif case == 1:
            env = module.safe_environment({"PATH": "/bin", "LANG": "C", "API_KEY": "secret", "DATABASE_URL": "secret", "HOME": "/secret"})
            require(env == {"PATH": "/bin", "LANG": "C"}, "Use a small environment allowlist")
            approvals = []
            require(module.authorize({"kind": "read"}, lambda a: False) is True, "Allow a structured read")
            for kind in ["network", "unknown", "bash", "delete"]:
                raises(PermissionError, lambda: module.authorize({"kind": kind}, lambda a: False))
            require(module.authorize({"kind": "bash", "command": "pwd"}, lambda a: approvals.append(a) or True), "Accept explicit approval")
            require(approvals == [{"kind": "bash", "command": "pwd"}], "Approve the exact structured action")
            raises(PermissionError, lambda: module.authorize({"kind": "delete"}, lambda a: "yes"))
        else:
            calls = []
            def diff_runner(args, **kwargs):
                calls.append((args, kwargs))
                return SimpleNamespace(returncode=0, stdout="- old\n+ new", stderr="")
            require("+ new" in module.inspect_changes(directory, diff_runner), "Return inspected changes")
            args, kwargs = calls[0]
            require(args == ["git", "diff", "--no-ext-diff", "--no-textconv", "--", "."] and kwargs["cwd"] == directory and kwargs["timeout"] == 5, "Disable diff hooks and set limits")
            raises(RuntimeError, lambda: module.inspect_changes(directory, lambda *a, **k: SimpleNamespace(returncode=1, stderr="not a repository")))


def run(task_id, add_result, criteria):
    key = task_id.removeprefix("mini-swe-phase-")
    for case, criterion in enumerate(criteria):
        try:
            with tempfile.TemporaryDirectory(prefix="mini-swe-phase-") as directory:
                check(key, case, directory)
            add_result(criterion, True, "Behavior check passed.")
        except Exception as exc:
            add_result(criterion, False, f"{type(exc).__name__}: {exc}")
