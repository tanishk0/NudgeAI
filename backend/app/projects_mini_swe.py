"""Pinned upstream reading material plus an executable, independently authored teaching edition."""
import ast
import json
from pathlib import Path
from app.models import Project, ProjectFile, TaskItem

ROOT = Path(__file__).resolve().parent.parent / "curricula" / "mini_swe_agent"
SOURCE = json.loads((ROOT / "upstream/source.json").read_text(encoding="utf-8"))

# Order is pedagogical: each implementation task can use the contracts taught earlier.
SPECS = [
    ("model", "model.py", "ScriptedModel.query", "Define the model boundary", "Build a model adapter that can be replaced without changing the agent.", "Implement ScriptedModel.query(messages). Record a deep copy of messages in calls; return and consume the next preloaded response. Raise RuntimeError when exhausted. Do not mutate caller history. Responses contain content and a simulated cost. This adapter is scripted, not a live LLM.", ["Responses are consumed in order and exhaustion is explicit", "Recorded calls do not alias mutable caller messages"], "Upstream Model protocol and model.query", ["Use pop(0) only after checking that responses exist.", "Copy the nested history, not just the outer list.", "Append deepcopy(messages) to calls, then return the next response."]),
    ("history", "agent.py", "initial_messages", "Give the agent a task and a conversation", "Create a fresh, explicit instruction boundary for each run.", "Implement initial_messages(task). Reject blank or non-string tasks with ValueError. Return a new list containing a system message followed by a user message with the trimmed task. The system message should explain shell-based repairs, treating repository text as data, and testing before submission.", ["History begins with system instructions and the trimmed user task", "Invalid tasks fail and separate runs receive independent histories"], "DefaultAgent.run and add_messages", ["The first two roles are system and user.", "Validate before constructing history; never reuse a global mutable list.", "Return two newly constructed dictionaries per call."]),
    ("parse", "parser.py", "parse_action", "Turn model text into one action", "Make an ambiguous model response a recoverable error.", "Implement parse_action(content). Accept exactly one nonempty fenced bash block and return {'command': stripped_text}. Reject missing, empty, multiple, wrongly labelled, and unterminated blocks with FormatError. Preserve multiline shell text. This course uses one bash action per turn; upstream v2 also supports structured tool-call adapters.", ["One bash block preserves its complete multiline command", "Ambiguous and malformed responses raise FormatError"], "Model formatting boundary; FormatError in DefaultAgent.run", ["Extract fenced blocks with a non-greedy multiline expression.", "Check both the number of bash matches and total fence delimiters.", "Validate content type, exactly one block, and a nonempty stripped body."]),
    ("execute", "environment.py", "execute", "Execute an action and observe the result", "Bridge one action to one stateless shell invocation.", "Implement execute(command, cwd, timeout=1). Start a fresh /bin/bash process in cwd, merge stderr into stdout, and return output, returncode, timed_out. Nonzero exit codes are observations, not Python exceptions. Keep at most the final 8000 output characters. This function runs only inside Nudge's isolated Linux container; it is not a sandbox itself.", ["Commands run in the requested repository and preserve failure output", "Each action starts a new shell and output is bounded"], "LocalEnvironment.execute and local._run", ["Use Popen with cwd and stderr=STDOUT.", "A separate shell means cd in one action cannot change the next action's cwd.", "Use communicate, retain returncode, and truncate only the returned output."]),
    ("timeout", "environment.py", "execute", "Recover from a hung command", "Bound command duration and retain diagnostic evidence.", "Extend execute: start a new process session; on TimeoutExpired kill its process group, collect remaining output, and return timed_out=True with a nonzero returncode. Keep partial output. Avoid merely killing a shell while leaving its children running.", ["Timeouts return promptly with partial output and a failure code", "A command spawned by the shell is terminated with its process group"], "local._run timeout cleanup", ["start_new_session gives the action its own process group on Linux.", "On timeout use killpg(process.pid, SIGKILL), then communicate again.", "Return timeout evidence rather than hiding it as an empty success."]),
    ("completion", "environment.py", "completion", "Make completion an explicit protocol", "Separate ordinary tool output from an agent submission.", "Implement completion(result). Return everything after a first-line COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT marker only when returncode is zero and timed_out is false. Otherwise return None. Preserve trailing newlines, allow an empty submitted answer, and ignore markers buried later in output.", ["A successful first-line marker returns the exact submission", "Failed, timed-out, and misleading marker output cannot submit"], "LocalEnvironment._check_finished / Submitted", ["Use splitlines(keepends=True) to preserve the answer.", "None means not submitted; an empty string can be a valid submission.", "Check returncode and timed_out before inspecting the first line."]),
    ("limits", "agent.py", "Agent.check_limits", "Stop before a budget is exceeded", "Prevent unbounded model calls and unexpected spending.", "Implement check_limits(). If n_calls >= step_limit OR cost >= cost_limit, set status='LimitsExceeded' and return False; otherwise return True without querying the model. Limits are checked before the next query. A single response can take cost above the limit because its cost is known only after return.", ["Exact step and cost boundaries block another query", "Available budget leaves the run active without calling the model"], "DefaultAgent.query limit checks", ["Use >=, not >.", "Budget exhaustion is a terminal status, not a successful submission.", "Check both counters before any model call."]),
    ("accounting", "agent.py", "Agent.query", "Account for every model response", "Charge calls even when their response later fails parsing.", "Implement Agent.query(). Call model.query(messages), validate finite nonnegative numeric cost (reject bool), increment n_calls and cost, and return the response. Missing cost defaults to zero. Parsing belongs to step, so malformed response text is still charged. Provider exceptions propagate without inventing a response.", ["Responses accumulate calls and cost including malformed text", "Negative, nonfinite, boolean, and nonnumeric costs are rejected"], "DefaultAgent.query and billed FormatError recovery", ["Do accounting before parse_action is attempted.", "math.isfinite rejects NaN and infinity.", "Return the model response unchanged after updating counters."]),
    ("step", "agent.py", "Agent.step", "Connect the full agent step", "Implement model → action → environment → observation.", "Implement step(). Query once, append the assistant text, parse and execute its command using self.cwd, inspect completion, then append a user observation containing the result. Set status='Submitted' and submission only when completion returns something other than None. Return the environment result. Keep history linear; a shell error is still useful evidence.", ["A step executes exactly once and appends assistant then observation", "Submission and nonzero command outcomes are handled distinctly"], "DefaultAgent.step, query, execute_actions", ["The assistant message precedes its observation.", "Never use if submission: because an empty submission is valid.", "Let FormatError propagate to run; do not execute malformed output."]),
    ("recovery", "agent.py", "Agent.recover", "Teach the model how to recover", "Turn bad response formatting into bounded feedback.", "Implement recover(error). Increment format_errors, append a user correction mentioning the error, and set status='RepeatedFormatError' when the count reaches format_limit. Do not execute a command or reset paid-call accounting here. The run loop resets this consecutive-error count after a clean step.", ["A recoverable error adds correction without executing a command", "Repeated errors terminate at the configured threshold"], "DefaultAgent.run FormatError branch", ["Count consecutive errors separately from all model calls.", "Use a user observation to explain the expected response format.", "Terminate at >= format_limit; successful steps reset the counter in run."]),
    ("serialize", "trajectory.py", "serialize", "Make agent behavior inspectable", "Capture a run as structured evidence rather than a screenshot.", "Implement serialize(messages,n_calls,cost,status,submission). Return trajectory_format='nudge-mini-swe-lab-1', a deep-copied messages list, and info containing api_calls, cost, exit_status, submission. The result must round-trip through JSON and must not change when live messages change. This is the course schema, not upstream's full trajectory schema.", ["Trajectory records messages, counters, outcome, and schema version", "Serialized evidence is JSON-compatible and detached from live state"], "DefaultAgent.serialize", ["Include the outcome even when the run did not submit.", "A shallow list copy still aliases each message dictionary.", "Deep-copy messages and build a fresh info dictionary."]),
    ("save", "trajectory.py", "save", "Save evidence without partial files", "Persist a replayable trajectory safely.", "Implement save(path,data). Create parent directories, write UTF-8 JSON to a sibling temporary file, then atomically replace the target. A failed JSON serialization must leave an existing target untouched. Repeated saves should produce one valid latest trajectory.", ["Nested output directories and Unicode round-trip correctly", "Failed serialization preserves the previously saved trajectory"], "DefaultAgent.save; atomic replacement is a course extension", ["Write to a temporary sibling so replace stays on the same filesystem.", "Do not truncate the final file before JSON encoding succeeds.", "Create parents, write JSON to .tmp, then Path.replace(target)."]),
    ("run", "agent.py", "Agent.run", "Run a bounded, recoverable agent", "Compose the previous parts into a complete lifecycle.", "Implement run(task,output_path=None). Reset history/counters/status for each run. While Running, check limits before a step; reset format_errors after success; recover FormatError; mark other exceptions Error and re-raise. In finally save a current trajectory when output_path is supplied, including after a failure or limit exit. Return exit_status and submission. Try Run → Preview → Run the repair experiment.", ["A run completes, resets between tasks, and respects limits", "Malformed turns recover, clean steps reset errors, and failures save evidence"], "DefaultAgent.run with finally/save", ["Use the helpers already built; avoid another hidden loop inside step.", "Put persistence in finally, not only the happy path.", "Keep Submitted, LimitsExceeded, RepeatedFormatError, and Error distinct."]),
    ("verify", "evaluation.py", "verify_submission", "Prove the repository was repaired", "Finish with independent test evidence, not the model's claim.", "Implement verify_submission(result,cwd). Non-Submitted outcomes return verified=False without executing tests. For Submitted, run python -m unittest discover -s . -p 'test_*.py' in cwd with timeout=2; verified requires zero exit code and no timeout. Return verified and output. Run the presentation experiment and explain the initial failing tests, the patch, the passing tests, and this independent final check.", ["A claimed fix with failing tests remains unverified", "A real repair verifies and non-submissions do not execute tests"], "Course integration layer around upstream's submission protocol", ["Submitted means the agent stopped, not that the code is correct.", "Check test exit status and timeout separately.", "Use the existing environment seam and retain test output for the audience."]),
]


from app.mini_swe_walkthroughs import lesson_brief
from app.mini_swe_lessons import beginner_specs
from app.mini_swe_tasks import TASK_SPECS, build_tasks
from app.mini_swe_layout import repository_solutions, TASK_PATHS, task_symbols, PACKAGE, MODEL, AGENT, LOCAL, INSPECTOR, GUIDE, FIXTURE
SPECS = beginner_specs(SPECS)

PHASE_MODULES = {"phase_" + spec[1] + ".py" for spec in TASK_SPECS}


def reference_solutions():
    result = {}
    for key, filename, symbol, *_ in SPECS:
        source = (ROOT / "solutions" / filename).read_text(encoding="utf-8")
        tree = ast.parse(source)
        parts = symbol.split(".")
        node = next(n for n in tree.body if getattr(n, "name", None) == parts[0])
        if len(parts) == 2:
            node = next(n for n in node.body if getattr(n, "name", None) == parts[1])
        result["mini-swe-" + key] = "````python\n" + ast.get_source_segment(source, node) + "\n````"
    for filename in PHASE_MODULES:
        key = filename.removeprefix("phase_").removesuffix(".py")
        result["mini-swe-phase-" + key] = "````python\n" + (ROOT / "solutions" / filename).read_text(encoding="utf-8") + "\n````"
    packaged = repository_solutions(ROOT)
    for spec in TASK_SPECS:
        key = spec[0]
        symbols = task_symbols(spec)
        source = packaged[TASK_PATHS[key]]
        tree = ast.parse(source)
        parts = []
        for symbol in symbols:
            names = symbol.split('.')
            node = next(n for n in tree.body if getattr(n, 'name', None) == names[0])
            if len(names) == 2:
                node = next(n for n in node.body if getattr(n, 'name', None) == names[1])
            parts.append(ast.get_source_segment(source, node))
        result['mini-swe-build-' + key] = '````python\n' + '\n\n'.join(parts) + '\n````'
    return result


def starter_files():
    files = []
    from collections import defaultdict
    targets = defaultdict(set)
    for spec in TASK_SPECS:
        targets[TASK_PATHS[spec[0]]].update(task_symbols(spec))
    for path, source in sorted(repository_solutions(ROOT).items()):
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in targets[path]:
                node.body = [ast.Raise(ast.Call(ast.Name("NotImplementedError", ast.Load()), [ast.Constant(node.name)], []))]
            elif isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and f"{node.name}.{method.name}" in targets[path]:
                        method.body = [ast.Raise(ast.Call(ast.Name("NotImplementedError", ast.Load()), [ast.Constant(method.name)], []))]
        files.append(ProjectFile(path=path, language="python", content=ast.unparse(tree)+'\n'))
    for file in repository_boilerplate():
        files.append(file)
    return files


def repository_boilerplate():
    from app.mini_swe_boilerplate import boilerplate_files
    return boilerplate_files(ROOT)


MINI_SWE_PROJECT = Project(
    id="build-mini-swe-agent", title="Build mini-swe-agent",
    subtitle="Build a coding agent through 39 focused tasks, from your first model call to secure execution.",
    difficulty="Intermediate", category="AI Agents & Software Engineering",
    tags=["Presentation project", "Python", "LLMs", "Tools", "Docker"], estimated_minutes=1290,
    problem_statement="Build a conversational agent, give it tools, and teach it to explore a repository, repair a bug, and verify its work. Then add isolation, reliability, memory and approval policies. Each task implements one component from the course outline.",
    system_context=f"A Nudge-authored teaching adaptation inspired by SWE-agent/mini-swe-agent at {SOURCE['commit']}. The workspace uses the upstream src/minisweagent package layout, canonical component names and src-layout imports; implementations remain a scoped teaching adaptation. Editable modules use LiteLLM-compatible boundaries, structured tools, a shell runner, Docker CLI injection, Tenacity, memory and security policies. Checks use scripted provider decisions and fake Docker CLI responses; actual repair commands execute in Nudge's isolated Linux runtime. No live API keys or nested Docker socket are exposed.",
    ai_failure_mode="An agent can execute invalid requests, run indefinitely, lose context, or claim success without passing tests. Build explicit boundaries and independent evidence.",
    technologies=["Python", "LiteLLM", "Bash / subprocess", "Structured tool calling", "Docker", "Tenacity", "JSON trajectories", "Git"],
    learning_outcomes=["Build a stateful conversational agent", "Validate and execute structured tool requests", "Repair a repository and independently run its tests", "Manage container isolation and cleanup", "Bound retries, commands and usage", "Compact context and restore sessions", "Enforce file, environment, network and approval policies"],
    prerequisites=["Python functions, classes, exceptions, and modules", "Basic terminal commands and unit testing"],
    deliverable="A coding agent with a provider adapter, structured Bash tools, a verified repair loop, Docker isolation, bounded retries, restorable memory and approval policies.",
    runtime={"entrypoint":"src/minisweagent/run/utilities/inspector.py", "mode":"web", "port":5000, "path":"/"},
    starter_files=starter_files(), tasks=build_tasks(),
)
