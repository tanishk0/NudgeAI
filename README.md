# Nudge

Learn software engineering by building and reviewing real projects with a code-aware AI mentor.

## The experience

1. Browse the catalogue and read a dedicated project brief: what you will build, learning outcomes, prerequisites, technologies, difficulty, time, and task roadmap.
2. Start your private workspace. Explore real files in Monaco and work through small tasks with explicit acceptance criteria.
3. **Run** starts an isolated application or console demonstration. **Check task** runs deterministic acceptance checks and reviews the result.
4. Use progressive hints or ask the mentor a question. Chat reads source and saved verification evidence; asking a question does not execute code.
5. Save a checkpoint, restore an earlier version, or export your source as a ZIP.

The catalogue has six projects and 58 tasks. **Build mini-swe-agent** has 39 individual tasks focused on agent behavior; project and environment setup are supplied by Nudge. Each has a focused implementation target, acceptance checks, hints, reference code, and a dedicated **Learn the concept** page linked from the brief and workspace. **DevShelf** is an eight-task beginner Flask/SQLite project. Other projects cover webhooks, tenant isolation, query batching, and application security.

### mini-swe-agent presentation project

The project appears first in the catalogue with the Presentation project tag. Its 39 tasks cover LLMs and conversation state, structured tools and subprocess execution, autonomous repair, containers, reliability, memory, and security. Topics are implemented as individual tasks rather than large phase assignments. Plan roughly 18–26 hours for the full course.

Checks inject provider completions and the Docker CLI; they do not consume API credits or expose a host Docker socket. Real shell commands repair a disposable buggy repository in the integration task. Tenacity is preinstalled. Run opens the inspector using the learner's shell, tools and autonomy components. See `docs/index.md` in the learner workspace for the learning workflow.

The workspace follows the pinned upstream repository layout: `src/minisweagent/models/litellm_model.py`, `agents/default.py`, `environments/local.py`, `environments/docker.py`, model utilities, serialization utilities, configuration, run scripts, and a matching `tests/` tree. The model and coordinator are named `LitellmModel` and `DefaultAgent`. Packaging, imports and CLI plumbing are supplied. Existing flat workspaces receive a checkpoint before their implementations move to the package paths; superseded teaching files leave the active tree. The original files remain in that checkpoint. Component paths are checked against `backend/curricula/mini_swe_agent/upstream/layout.json` from the pinned GitHub commit.

Original upstream core files and MIT attribution are pinned under `backend/curricula/mini_swe_agent/upstream/`. Editable learner modules are an explicit teaching adaptation, not the complete upstream package. The repair experiment uses a visibly labelled scripted model to avoid live-provider outages; actual commands, patches, tests, and saved trajectories are real. This does not change Nudge authentication or enable the application's local demo mode.

The workspace includes `PRESENTATION.md` with a six-minute presentation sequence, rehearsal checklist, and answers about what is scripted versus implemented. To create a completed instructor-only rehearsal export:

```powershell
cd backend
.venv/Scripts/python.exe -m app.prepare_mini_swe_presentation
```

The ZIP is saved in ignored `backend/.rehearsal/`; it is not returned by public project APIs. Run exported shell-executing code only in an isolated Linux container. New course records are inserted by normal application startup or `python -m app.seed`; existing learner workspaces remain pinned.

## Development

Requirements: Node.js 24+, Python 3.12+, PostgreSQL/Supabase, and Docker Desktop with Linux containers for Run and Check task.

### Backend

```powershell
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Copy `backend/.env.example` to `backend/.env` and supply your database, Supabase URL/publishable key, and optional NVIDIA credentials. Never put database credentials, service-role keys, or NVIDIA keys in frontend environment variables.

```powershell
# From the repository root, with Docker running:
docker build -t nudge-runtime:local backend/runtime

cd backend
.venv/Scripts/python.exe -m app.migrations
.venv/Scripts/python.exe -m app.seed
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API currently uses **one worker** because preview leases, capability tickets, execution limits, and rate limits are process-local. Use a shared runtime manager and shared limits before scaling to multiple workers.

### Frontend

Copy `frontend/.env.example` to `frontend/.env`, using the same Supabase project as the backend.

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Configure `FRONTEND_URL` with the exact frontend origin; comma-separated origins are supported.

### Local demo without Supabase

This is an explicit development entry point with a separate SQLite database and a fixed demo identity. It does not modify or use your configured PostgreSQL database. Do not expose the demo API publicly.

```powershell
# Terminal 1
cd backend
.venv/Scripts/python.exe demo.py

# Terminal 2
cd frontend
$env:VITE_DEMO_MODE = 'true'
npm run dev -- --host 127.0.0.1 --port 5174
```

Open `http://localhost:5174/projects`. Demo authentication is available only in Vite development mode. Production builds always use Supabase authentication. Run and Check task still require Docker. Demo data is stored in ignored `backend/.demo/`.

## Storage and curriculum

- `projects` is the catalogue. Startup inserts missing projects; it does not overwrite existing definitions.
- `project_versions` stores immutable authored definitions, including private mentor material.
- `workspace_states` pins a session to its curriculum version and tracks a workspace revision.
- `workspace_files` stores one text file per row. Unchanged file contents are not rewritten.
- `workspace_snapshots` retains the most recent 20 checkpoints. Reset and restore checkpoint the previous files first.
- `workspace_runs` records the revision, content hash, and result of execution and verification.
- Chat and progress remain associated with the authenticated workspace.

Existing JSONB workspaces are copied into file rows and pinned on first load. Legacy JSONB files remain intact as migration input; subsequent edits use the file table. Existing completed tasks without matching content hashes must be checked again.

`python -m app.migrations` applies a versioned additive bootstrap recorded in `schema_migrations`. PostgreSQL uses an advisory lock while applying the migration. No legacy tables or learner records are deleted.

To publish edited curriculum for **new** workspaces:

```powershell
cd backend
.venv/Scripts/python.exe -m app.seed --publish
```

Existing workspaces normally keep their pinned definitions. The requested mini-swe roadmap replacement is explicit: after publishing, the next load creates a checkpoint and another immutable course version with the current individual tasks. It preserves saved files and merges compatible implementations into the new scaffolds, adding missing helpers. Obsolete completion/hint records no longer appear in the new roadmap; each new task must be checked independently. The previous version and checkpoint remain available for recovery. Other courses remain pinned as before.

## Saving and recovery

Every mutation requires `expected_revision`. PostgreSQL row locks serialize workspace changes; a stale writer receives HTTP 409 rather than overwriting another tab. The client serializes saves and file mutations, acknowledges the saved file contents, and keeps newer editor changes dirty.

Local recovery copies are scoped to the user and project in browser storage. A recovered draft is offered explicitly after reload. Choosing Restore local edits applies the draft against the currently loaded server version; Keep server version discards that local draft.

Text workspaces are limited to 100 files, 256 KB per file, and 2 MB total. Paths are normalized and checked for traversal, absolute/drive paths, reserved runtime names, case collisions, and file/directory conflicts. Starter reference files are protected on the server. Binary asset upload is not included in this version.

## Execution and preview

Learner code never runs in the API's Python interpreter. Each execution gets a non-root Docker container with a read-only root filesystem, dropped Linux capabilities, CPU/memory/process limits, bounded logs, temporary writable storage, and **network disabled**. Only the input workspace is mounted read-only; platform environment variables and credentials are not passed into the container.

Web previews start Flask in that environment. An author-controlled HTTP bridge executed through Docker forwards preview requests over container loopback, so no container ports are published. The API issues a random 10-minute capability URL for iframe subrequests and serves responses with sandbox restrictions. Platform cookies and authorization headers are never forwarded. Treat a capability URL as private while it is valid.

Preview databases and other generated runtime files are temporary. Stopping or restarting a preview starts fresh runtime data; saved source files remain in the database. Previews stop after ten minutes or on a clean API shutdown. The UI reports which revision is running; saved edits require a new run.

The deterministic checks are learning feedback, not a tamper-resistant examination system. Results are validated against the expected criterion set and bound to a source hash, but learner code and exercise checks share an isolated process. A hostile learner can potentially manipulate that process. A high-stakes assessment service needs a separate trusted evaluator protocol.

## AI mentoring

The mentor receives project goals, task criteria, the roadmap, numbered target/focused code, relevant local imports, a bounded diff, and verification evidence only when it matches the current source hash. Private author hints and briefings are removed from public API models. Learner source is treated as untrusted context rather than system instructions.

Three hints progressively increase specificity without code. The fourth reveals the active task's reference solution and allows mentor chat to explain code, including line-by-line walkthroughs. Both endpoints use the task's persisted hint level, so chat cannot unlock code or inherit another task's unlock. Before unlock, reference solutions are withheld from the prompt and completed answers pass a conservative syntax detector before display. A rejected answer gets one rewrite attempt; repeated violations or provider failures save no assistant response and advance no hint. The detector is a heuristic for common code forms, not a proof against every possible encoding of code.

Mentor endpoints stream provider responses. Before unlock, the server holds text until the completed answer passes the output check, while the connection sends keepalives. After unlock, code can stream normally. Missing credentials and provider errors return an unavailable response rather than an authored answer presented as AI. AI feedback does not determine task pass/fail.

Changing source makes old verification results stale. Checking a task also rechecks previously completed tasks against the same source snapshot. A workspace edit during checking returns a revision conflict rather than attaching an old result to new code.

## Verification

```powershell
cd frontend
npm run build
npm run lint

cd ../backend
.venv/Scripts/python.exe -m unittest discover -s tests -v

# Include container execution and preview integration tests:
$env:NUDGE_DOCKER_TESTS = '1'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Tests use a disposable SQLite database by default. Supply `NUDGE_TEST_DATABASE_URL` pointing to a **disposable PostgreSQL database** to also test concurrent row-lock behavior. Tests create tables, catalogue entries, and test workspaces in that database. They never use `backend/.env` as the test database.

GitHub Actions builds/lints the frontend and runs the backend suite against PostgreSQL and Docker. Provider-backed authentication and live NVIDIA responses require configured credentials and separate integration testing.

## Next deployment steps

Use the normal Supabase-authenticated entry point, a valid PostgreSQL connection, HTTPS, and an exact frontend origin. For a public multi-user deployment, separate the privileged container runner from the API host and move execution jobs, leases, limits, and preview routing into a durable worker service. This repository currently supplies the local/single-worker runtime implementation; it does not provision hosted infrastructure.
