"""Seven additive capstone tasks and public, concept-first lessons."""
from app.models import TaskItem

PHASES = [
    {
        "key": "core", "title": "Core agent and LLM integration", "estimate": "3–4 hours",
        "items": ["Project initialization and virtual environment", "Model class using LiteLLM", "Agent class", "Conversation state management", "Basic execution loop"],
        "outcome": "A functional conversational agent.",
        "contract": "Implement Model.__init__(name, complete=None), Model.query(messages, tools=None), and ConversationAgent.__init__, chat(text), run(inputs) in phase_core.py. Validate a nonblank model name and chat text. Lazily import litellm.completion only when complete is absent. Call it with model and a deep copy of messages; when tools are supplied include tools and tool_choice='auto'. Accept a dictionary response or an object with model_dump(); return choices[0].message as a detached dictionary. Each agent owns its system-first history. chat adds the trimmed user text, queries once, records the assistant reply, and returns its content (empty string for null). run processes the input iterable in order. Add virtual-environment setup and LiteLLM installation notes to your project README; do not install packages through the learner shell.",
        "criteria": ["The injected completion receives model, independent history, and optional tools", "Conversation state persists across turns and stays independent between agents", "Invalid input is rejected and a sequence of inputs produces ordered replies"],
        "lesson": """### From a function call to a conversation
A language model receives messages and produces the next message. Your **Model** class is an adapter: the agent talks to one stable Python interface while LiteLLM handles the provider request. Dependency injection means supplying the completion function as an argument. It lets a test return a prepared provider response while the exported implementation can call a real provider.

### Initialize a project you can reproduce
A virtual environment gives this project its own packages. In an exported project, create it with `python -m venv .venv`, activate it, and install LiteLLM in that environment. Record dependencies in a requirements file. Keep credentials in the trusted provider process, outside the repository and command environment. The hosted learning runner is offline; it uses an injected completion and does not install packages during a task check.

### State belongs to the agent
The message list is the agent's conversation state. Start with a system message describing behavior, then alternate user requests and assistant responses. A new agent needs a new list. A deep copy also separates nested dictionaries; copying only the outer list leaves shared message objects.

### Walk through one turn
```python
history = [{"role": "system", "content": "Explain Python clearly."},
           {"role": "user", "content": "What is a list?"}]
provider_reply = {"choices": [{"message": {
    "role": "assistant", "content": "A list stores an ordered collection."}}]}
```
The adapter extracts the message from the provider envelope. The agent appends that message before accepting another user input. A basic loop repeatedly performs this same turn; no command execution is involved yet.

### Think before you build
Why does passing the live list directly to a provider wrapper risk changing your recorded history? How would a second agent accidentally inherit the first conversation?

### Common mistakes
Avoid mutable default arguments such as `messages=[]`. Keep provider transport details out of the Agent class. Do not mistake a scripted test response for a demonstration of live reasoning.

Read more: [LiteLLM completion](https://docs.litellm.ai/docs/completion).""",
    },
    {
        "key": "tools", "title": "Tool calling and execution", "estimate": "3–4 hours",
        "items": ["Define Bash tool schema", "Bind tools to the LLM", "Parse tool calls and arguments", "Execute commands using subprocess", "Capture command output and return codes", "Feed tool results back into the LLM"],
        "outcome": "An agent capable of reading, creating and modifying files.",
        "contract": "Implement bash_schema(), parse_tool(call), and tool_turn(model, messages, cwd, runner=execute) in phase_tools.py. The Bash function schema requires one string command and rejects additional properties. parse_tool accepts only a function call named bash with a nonempty string id and JSON object containing exactly one nonblank command; invalid requests raise ValueError. Validate every call and unique ids before executing any. Bind the schema through model.query(messages, tools=[bash_schema()]); append a deep-copied assistant response, then one role='tool' observation per call with matching tool_call_id and JSON-encoded runner result. Call runner(command, cwd, timeout=2). Its subprocess implementation is the environment.execute function from the foundation tasks. Preserve nonzero return codes and timeouts in the observation.",
        "criteria": ["The Bash schema and strict parser accept valid calls and reject malformed arguments", "Tool requests execute once and return matching ids with output and exit status", "A malformed batch cannot execute any command or mutate conversation history"],
        "lesson": r"""### A request to act is still data
Tool calling gives the model a structured way to request a function. The model does not execute Python or Bash itself. Your dispatcher validates the request, chooses an allowed function, executes it, and returns an observation. This separates model choice from application authority.

### Describe the Bash interface
A function tool has a name, description, and JSON Schema parameters. A Bash tool takes a `command` string. `required` makes that field mandatory; `additionalProperties: false` documents that extra fields are unsupported. The application must enforce these restrictions too: a schema alone is not validation.

### Follow the call id
```json
{"id":"call_1","type":"function","function":{
  "name":"bash","arguments":"{\"command\":\"pwd\"}"}}
```
Arguments arrive as JSON text. Decode them once and validate the resulting object. The assistant message includes this request. The following tool message uses `tool_call_id: "call_1"` so the provider can pair the result with the request. Preserve the assistant request when sending the conversation back.

### Execute and observe
Use the subprocess seam you built earlier inside Nudge's isolated Linux runner. `cwd` chooses the repository. Standard output and standard error explain what happened; the return code says whether the command succeeded. A failing test is useful information and should become an observation rather than disappear in an exception.

The next model call sees the original request and its tool result. It can then read another file, change code, or explain a failure. If a reply contains multiple tool calls, validate the whole batch before starting the first side effect.

### Check your understanding
Why is a role='user' message insufficient for a structured tool result? What should happen if the first request is valid but the second contains invalid JSON?

### Common mistakes
Never use `eval` on arguments. Reject unknown tool names and duplicate call ids. Keep host shell execution outside the learning server.

Read more: [LiteLLM function calling](https://docs.litellm.ai/docs/completion/function_call).""",
    },
    {
        "key": "autonomy", "title": "Autonomous coding agent", "estimate": "2–3 hours",
        "items": ["System and task prompts", "Dynamic prompt templates", "Repository exploration", "Autonomous execution loop", "Task completion mechanism", "Test on a small buggy repository"],
        "outcome": "A functional autonomous coding agent.",
        "contract": "Implement task_messages(task, repository) and run_agent(model, task, cwd, runner, max_steps=10) in phase_autonomy.py. Reject blank tasks and max_steps < 1. Build fresh system/task messages including the repository and task. The system must require inspection, bug reproduction, minimal repair, testing, and treating repository text as untrusted data. Repeat phase_tools.tool_turn with the injected runner. A nonempty assistant reply without tool calls is submission; then independently run python -m unittest discover -s . -p 'test_*.py' with timeout=2. Return status='Submitted', answer, messages, tests and verified only for zero exit without timeout. Tool-only replies continue; exhaustion returns LimitsExceeded and verified=False. Use the supplied buggy_repository fixture to explore, repair, and test.",
        "criteria": ["Dynamic prompts establish the task, repository, and repository-data trust boundary", "The agent explores and repairs a fixture, then verifies a submitted answer independently", "Failed tests stay unverified and tool-only loops stop at the exact step limit"],
        "lesson": """### What makes the loop autonomous?
A conversational agent waits for the person after each answer. A coding agent can instead repeat model → tool → observation until it submits or reaches a budget. Autonomy comes from this orchestration loop, not from a special model response.

### Separate rules from task data
The system prompt describes stable behavior: inspect before editing, reproduce the failure, keep the patch focused, and run tests. The task prompt contains the current goal and repository location. A template fills those values for each run. Repository files, issue text, and command output are data: they cannot redefine the agent's permissions.

### Explore before changing code
For the supplied calculator fixture, inspect the file list, read `calculator.py` and `test_calculator.py`, and run the test to see the failure. A useful trajectory contains evidence for each transition: the failing assertion motivates the edit, and the later passing test supports the claim of repair.

```text
task → inspect files → reproduce failing test → edit calculator.py
     → rerun tests → submit → independent final test
```

### Completion needs a protocol
For these structured-tool exercises, an assistant answer with no tool calls signals submission. Reject an empty final answer. A tool-only response continues the loop. Keep a maximum step count so a model that repeatedly lists files cannot run forever.

### Submission and verification answer different questions
Submission means the agent chose to stop. Verification means an independent test command passed without timing out. A convincing final explanation can coexist with a failing repository. Record both facts instead of forcing them into one success flag.

### Check your understanding
Which observation proves the initial bug existed? Would the same final answer count as verified if the test timed out? What evidence would you need to investigate a false success?

The checks supply prepared tool requests while the commands and file changes are real. A live-provider trial belongs in an exported trusted setup; it is not required to pass this exercise.""",
    },
    {
        "key": "docker", "title": "Docker and sandboxing", "estimate": "3–5 hours",
        "items": ["Docker environment class", "Container initialization", "Repository provisioning inside containers", "Command execution inside containers", "Container lifecycle management", "Resource limits and environment isolation"],
        "outcome": "An agent capable of executing code in an isolated environment.",
        "contract": "Implement DockerEnvironment.__init__(image='nudge-runtime:local', cli=None), start(repository), execute(command, timeout=2), and close() in phase_docker.py. Inject cli or use subprocess.run; give each instance a unique mini-swe- name and started=False. Start a detached named container with no network, read-only root, all capabilities dropped, no-new-privileges, user 1000:1000, 256m memory, one CPU, 64 pids, /work and /tmp tmpfs, and a read-only repository bind at /input. Set /work as cwd and copy /input/. into /work/ using docker exec. Use argument lists, checked startup and explicit timeouts. On startup/provisioning failure remove the container and re-raise. execute requires started, invokes /bin/bash -lc inside the container, merges returned stdout/stderr and keeps the last 8000 characters. A CLI timeout must remove the container, return partial output, nonzero returncode and timed_out=True. close removes the container even after partial startup and sets started=False. Checks inject a CLI double; no Docker socket is exposed in the learner container.",
        "criteria": ["Startup provisions a repository with network, resource, privilege and filesystem restrictions", "Commands execute inside the container and preserve bounded diagnostic output", "Timeouts and startup failures remove containers and clear running state"],
        "lesson": """### An execution interface can have different backends
Earlier, an environment started a local process inside Nudge's existing sandbox. Now build an environment adapter that addresses a container. The agent still asks for command output and exit status; the adapter owns where execution happens.

### Images, containers, and repositories
An image supplies the interpreter and tools. A container is one running instance of that image. Bind the source repository read-only at `/input`, then copy it into a writable `/work`. This lets the agent edit its working copy without overwriting the host repository. The working copy disappears when the container is removed.

### Set restrictions when creating the container
The task uses a non-root user, drops capabilities, disables privilege escalation, disables networking, and makes the root filesystem read-only. Dedicated tmpfs mounts provide bounded temporary writable space. CPU, memory, and process limits restrict resource use. A prompt asking the model to behave cannot replace these operating-system controls.

### Think in lifecycle states
```text
not started → container created → repository copied → commands running
                        ↘ failure → remove container
commands running → finished or timed out → remove container
```
Every failure path needs cleanup. A timed-out `docker exec` client does not guarantee that its command has stopped inside the container. Removing the container terminates its remaining processes, so this course treats a command timeout as the end of that environment.

### Test the boundary without nesting containers
Inject a CLI function that records argument lists and returns prepared process results. This checks which isolation options your code requests. It does not prove kernel isolation; a separate Docker integration test is needed for that. Nudge never mounts the host Docker socket into the learner sandbox.

### Check your understanding
Why copy a repository instead of giving the container a writable host bind? Which component should clean up if copying fails? What host resources could an unrestricted Docker daemon control?

Read more: [Docker run reference](https://docs.docker.com/reference/cli/docker/container/run/).""",
    },
    {
        "key": "reliability", "title": "Reliability and error handling", "estimate": "2–3 hours",
        "items": ["API retries using Tenacity", "Exponential backoff", "Custom exceptions", "Malformed tool call handling", "Command timeouts", "Token, cost, time and step limits"],
        "outcome": "An agent that can recover from common failures and terminate predictably.",
        "contract": "In phase_reliability.py define TransientAPIError, LimitsExceeded, and MalformedToolCall (a ValueError subtype). Implement retry_api(operation, attempts=3, sleep=time.sleep) with Tenacity Retrying, stop_after_attempt, wait_exponential(multiplier=1, max=8), retry_if_exception_type(TransientAPIError), injected sleep and reraise=True; attempts must be positive. Never retry validation errors. remaining_budget(usage, limits) checks steps, tokens, cost and seconds: require finite numeric nonboolean usage >= 0 and limits > 0; raise LimitsExceeded at any used >= limit, otherwise return True. safe_tool(call, cwd, runner) converts parse_tool ValueError to MalformedToolCall and never executes malformed requests; valid calls use timeout=2 and preserve timeout observations. Checks use real Tenacity with injected sleep; the package is preinstalled and no waiting or provider request is needed.",
        "criteria": ["Transient provider failures retry with bounded exponential waits; other failures propagate", "Exact token, cost, elapsed-time and step boundaries prevent further work", "Malformed tools never execute and command timeout evidence is preserved"],
        "lesson": """### First classify the failure
A temporary provider outage may succeed on retry. Invalid JSON needs a correction to the model. A command timeout needs process cleanup. A spent budget needs termination. Treating every exception as retryable can repeat side effects and waste the remaining budget.

### Bounded retries with Tenacity
Tenacity separates the decision to retry, when to wait, and when to stop. In this task, only `TransientAPIError` retries. The wait grows exponentially, with a cap; the attempt limit includes the initial call. Injecting `sleep` lets tests record delays without actually waiting.

```text
attempt 1 fails → wait 1 second
attempt 2 fails → wait 2 seconds
attempt 3 fails → propagate the error
```
The trusted provider adapter must classify real provider errors into transient and permanent categories. Do not wrap all exceptions as transient. If you later add a total time budget, the request timeout and retry waits must fit inside that remaining allowance.

### Multiple budgets protect different resources
Steps bound repeated decisions. Tokens bound model input and output. Cost bounds accumulated billing estimates. Elapsed seconds bound wall-clock duration. Check before starting another operation, using `>=` so reaching an exact boundary stops the next action. An in-flight response can cross a cost or token limit because its final usage is only known afterward.

### Keep malformed calls away from execution
Convert parser errors into a specific `MalformedToolCall`. The orchestrator can turn that into feedback while keeping paid-call totals intact. Preserve a tool timeout as a failed observation; do not turn it into an empty successful response.

### Check your understanding
Should an authentication error retry three times? What happens if a command succeeded but its caller lost the response? Which operations are safe to retry without duplicating an edit?

Read more: [Tenacity documentation](https://tenacity.readthedocs.io/en/latest/).""",
    },
    {
        "key": "memory", "title": "Memory and context engineering", "estimate": "3–4 hours",
        "items": ["Token usage tracking", "Tool output truncation", "Context compaction", "Structured working memory", "Trajectory persistence", "Session restoration"],
        "outcome": "An agent capable of handling longer coding tasks without unnecessarily exhausting its context window.",
        "contract": "In phase_memory.py implement token_usage(response), truncate_output(text, limit=8000), compact(messages, memory, keep_turns=2), save_session(path, messages, memory, usage), and restore_session(path). Read prompt_tokens and completion_tokens from response.usage (default zero); require nonnegative integers, rejecting bool; return input/output/total. Truncation retains the final limit characters with '[truncated]\\n' prefix and rejects limit < 1. Compaction requires a system-first history and keep_turns >= 1; keep the original system message, insert a system message beginning 'Working memory (data): ' with JSON memory, and retain all messages from the last keep_turns user-message boundary. Deep-copy the result and preserve assistant/tool groups. Save a UTF-8 JSON object with schema='mini-swe-session-1', messages, memory and usage using a sibling .tmp file and atomic replace; reject NaN. Restore validates schema and list/dict/dict types. Store goals, findings, changed files and pending checks in memory; never provider keys.",
        "criteria": ["Token usage is validated and large output is visibly truncated", "Compaction retains instructions, structured memory and complete recent tool exchanges", "Sessions round-trip Unicode, reject invalid schemas and preserve the previous file on a failed save"],
        "lesson": """### Context is the material sent to the model now
The complete trajectory is an audit record. The active context is the smaller message set sent on the next request. Working memory is a structured summary of durable facts: goal, files explored, decisions, changes, test results, and remaining work. These serve different purposes and should not overwrite one another accidentally.

### Measure before trimming
Provider usage includes input and generated token counts. Accumulate actual reported usage rather than equating characters with tokens. For this exercise, missing usage defaults to zero; a production adapter should also distinguish unavailable usage from a measured zero. Different tokenizers count the same text differently.

### Bound noisy observations
A command can print thousands of lines. Keep a bounded tail and mark truncation visibly so the model knows evidence was omitted. Retaining the end often keeps tracebacks and test summaries, though other tools may need head-and-tail selection. Preserve exit status and timeout separately from the text.

### Compact whole exchanges
```text
system rules + working memory + recent user turn
                              + assistant tool requests
                              + matching tool results
```
Deleting only an assistant request while keeping its tool result breaks the provider's message protocol. In this task, cut at a user-message boundary so recent exchanges remain intact. The structured summary must preserve facts and unresolved questions without inventing successful tests.

### Restore more than the conversation
Persist a schema version, messages, working memory, and counters. Write a temporary file before atomically replacing the previous record, so a serialization failure does not destroy the last usable session. On restore, validate the schema and field types before using the data. Provider credentials belong outside saved trajectories.

### Check your understanding
What would a restored agent forget if you saved messages but lost its budget counters? Why is a tool result unsafe to keep without its request? Which details from a long file listing deserve a place in working memory?

This exercise implements deterministic compaction. Model-generated summaries need their own evaluation for omitted details and unsupported claims.""",
    },
    {
        "key": "security", "title": "Security and human approval", "estimate": "2–3 hours",
        "items": ["Filesystem access restrictions", "Sensitive environment variable protection", "Network restrictions", "Human approval for sensitive actions", "Change inspection using Git diff"],
        "outcome": "A more controlled and secure coding agent.",
        "contract": "In phase_security.py implement allowed_path(root, candidate), safe_environment(source), authorize(action, approve), and inspect_changes(cwd, runner). Resolve paths and reject absolute input, paths escaping root (including symlinks), and components .git/.aws/.ssh/.env or beginning .env. Return a resolved Path for allowed relative input. safe_environment uses an allowlist containing only PATH, LANG, LC_ALL. authorize allows read/write, always denies network and unknown kinds, and requires approve(action) is True for bash/delete; denial raises PermissionError. Approval is for the exact structured action, not blanket permission. inspect_changes runs ['git','diff','--no-ext-diff','--no-textconv','--','.'] with cwd, capture_output=True, text=True and timeout=5; return stdout or raise RuntimeError on failure. Explain that this diff excludes untracked files, and that path checks cannot confine arbitrary Bash: use the Phase 4 container and deny unapproved shell commands.",
        "criteria": ["Repository-relative paths reject escapes, symlinks and sensitive files", "Environment secrets are excluded and network or sensitive actions require policy enforcement", "Git changes are inspected without external diff hooks and errors remain visible"],
        "lesson": """### Put authority outside the model
The model can suggest an action; the application decides whether it is allowed. System prompts help communicate expectations but do not constrain filesystem access, environment inheritance, or networking. Enforce those boundaries in trusted code and the execution environment.

### Filesystem restrictions need resolved paths
Join a relative path to the repository root and resolve it before checking containment. A path can escape through `..` or through a symlink that points outside the root. Reject sensitive directories and environment files even when they are inside the repository. These checks are useful for structured file tools; a shell can access paths without calling your helper, so keep shell execution inside the container as well.

### Start with a small command environment
Copying all of `os.environ` into a command can expose provider tokens, database passwords, and cloud credentials. An allowlist builds a small environment from explicitly permitted keys. The provider process and command process need separate credential scopes. For an exported runner, also validate the values of permitted variables and use trusted executable paths.

### Approval is a specific decision
```text
structured action → policy check → approval when required → execution
```
Ask about the exact command or destructive operation. A denial must prevent execution. A model saying that the person approved something is not approval. This lesson's policy always blocks network actions and requires an explicit boolean approval for shell and delete actions. Network enforcement also belongs in container configuration, because arbitrary shell commands can attempt network access.

### Review the actual patch
Use Git diff to show tracked modifications before a sensitive step. Disable external diff and text-conversion hooks so inspecting a diff does not execute repository-configured helpers. Plain diff does not include untracked files; pair it with a trusted status check and explicit inspection of new files in a complete review workflow.

### Check your understanding
Could a symlink pass a string-prefix check? Would a prompt stop `curl` from running? Which exact action did the person approve, and can that approval be reused after the command changes?

This is a teaching policy, not a replacement for Nudge's existing isolation and authentication.""",
    },
]


def phase_tasks(start_order=17):
    return [TaskItem(
        id="mini-swe-phase-" + phase["key"], order=start_order + index,
        title=f"Phase {index + 1} — {phase['title']}",
        category="security" if phase["key"] in {"docker", "security"} else "architecture",
        objective=phase["outcome"], target_file="phase_" + phase["key"] + ".py",
        instructions=f"**Estimated: {phase['estimate']}**\n\n### Build checklist\n" + "\n".join("- " + item for item in phase["items"]) + f"\n\n### Implementation contract\n{phase['contract']}\n\n### Outcome\n{phase['outcome']}\n\nSave and choose **Check task**. These checks use controlled provider/CLI doubles inside the existing sandbox. For the underlying ideas and examples, open **Learn the concept**.",
        validation_criteria=phase["criteria"],
        hints=["Read the concept page, then implement one function at a time using the named interfaces.", phase["contract"], "Inspect the failing acceptance criterion and compare your inputs, return values, and error paths with the task contract."],
        mentor_context="This is an additive mini-swe capstone. Teach the listed topics and exact function contracts. Tests inject dependencies; never ask the learner to expose secrets, enable network access, or mount a Docker socket in the sandbox.",
        phase=index + 1, estimated_time=phase["estimate"], concept_markdown=phase["lesson"],
    ) for index, phase in enumerate(PHASES)]


def attach_concepts(project):
    """Enrich old pinned tasks without changing their behavioral contracts."""
    from app.mini_swe_walkthroughs import PURPOSE, EXAMPLES
    for task in project.tasks:
        key = task.id.removeprefix("mini-swe-")
        if key in PURPOSE and not task.concept_markdown:
            why, goal, receives, produces = PURPOSE[key]
            explanation, example, expected = EXAMPLES[key]
            task.concept_markdown = (
                f"### Why this concept matters\n{why}\n\n### Understand the mechanism\n{explanation}\n\n"
                f"### Follow the data\n**Input:** {receives}\n\n**Output:** {produces}\n\n"
                f"### A worked example\n```python\n{example}\n```\n\n{expected}\n\n"
                f"### Connect it to your task\n{goal} Open `{task.target_file}` when you return to the workspace. "
                "Focus on this component's contract before implementing later parts of the agent.\n\n"
                "### Check your understanding\nBefore coding, explain what this component receives, what it changes, "
                "and what happens on invalid input. Trace the example by hand, then consider an empty input "
                "or a repeated call. Which state must remain independent between runs?\n\n"
                "### Try it\nReturn to the task, implement the missing behavior, and choose **Check task**. "
                "Compare each failed result with the input/output contract. Passing this task demonstrates "
                "one component; the final repair exercise checks the integrated agent."
            )
    return project
