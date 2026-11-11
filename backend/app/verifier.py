import difflib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import (
    CriterionEvaluation,
    Project,
    TaskItem,
    TaskVerificationReport,
    UpdateWorkspaceStateRequest,
    VerifyTaskRequest,
    WorkspaceFile,
    WorkspaceSessionResponse,
)
from app.vulpy_checks import VULPY_CHECKS_CODE
from app.workspace_service import (
    _get_project_and_session,
    _session_to_response,
    update_workspace_state,
)

DEFAULT_SANDBOX_TIMEOUT = 3.5

# Vulpy tasks hash passwords with scrypt (~60ms each) many times per run.
TASK_TIMEOUT_OVERRIDES: Dict[str, float] = {
    "vulpy-task-1-sqli": 10.0,
    "vulpy-task-2-password-storage": 10.0,
    "vulpy-task-3-password-change": 10.0,
    "vulpy-task-4-session-forgery": 10.0,
    "vulpy-task-5-api-keys": 10.0,
    "vulpy-task-6-xss-headers": 10.0,
}


def build_unified_diff(
    project: Project, current_files: List[WorkspaceFile]
) -> str:
    """
    Compute a unified diff between starter_files and the user's current_files
    so both the evaluator and AI mentor see exact line-by-line modifications.
    """
    starter_map = {f.path: f.content for f in project.starter_files}
    diffs: List[str] = []

    for wf in current_files:
        if wf.read_only:
            continue
        old_content = starter_map.get(wf.path, "")
        if old_content == wf.content:
            continue
        diff_lines = list(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                wf.content.splitlines(keepends=True),
                fromfile=f"starter/{wf.path}",
                tofile=f"user/{wf.path}",
                n=3,
            )
        )
        if diff_lines:
            diffs.append("".join(diff_lines))

    return "\n".join(diffs) if diffs else "(No changes made to starter files yet.)"


# Isolated Python runner script executed inside a temporary directory subprocess
SANDBOX_HARNESS_CODE = r'''
import ast
import hashlib
import hmac
import json
import re
import sys
import time
import traceback

task_id = sys.argv[1]
results = []
logs = []

def add_result(criterion: str, passed: bool, reason: str):
    results.append({"criterion": criterion, "passed": bool(passed), "reason": reason})
    status_str = "PASS" if passed else "FAIL"
    logs.append(f"[{status_str}] {criterion} -> {reason}")

try:
    if task_id.startswith("vulpy-"):
        # Vulpy security-review checks live in a separate module written next to this harness.
        import _vulpy_checks
        with open("_nudge_criteria.json", "r", encoding="utf-8") as f:
            _criteria = json.load(f)
        _vulpy_checks.run(task_id, add_result, _criteria)

    elif task_id == "task-1-timing-replay":
        with open("webhook_service.py", "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        import webhook_service as ws

        now = int(time.time())
        payload = b'{"id":"evt_1","user_id":"user_101","amount_cents":1000}'
        secret = ws.WEBHOOK_SECRET.encode("utf-8")

        # Valid bound signature: "{timestamp}.{payload}"
        bound_msg = f"{now}.".encode("utf-8") + payload
        valid_bound_sig = hmac.new(secret, bound_msg, hashlib.sha256).hexdigest()
        raw_unbound_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()

        # Expired bound signature (600s old)
        old_ts = now - 600
        old_bound_sig = hmac.new(secret, f"{old_ts}.".encode("utf-8") + payload, hashlib.sha256).hexdigest()
        future_ts = now + 600
        future_bound_sig = hmac.new(secret, f"{future_ts}.".encode("utf-8") + payload, hashlib.sha256).hexdigest()

        # 1. Replay window check (must accept valid current timestamp AND reject expired/future for both bound & unbound)
        accepts_now = (
            ws.verify_signature(payload, valid_bound_sig, now) is True
            or ws.verify_signature(payload, raw_unbound_sig, now) is True
        )
        rejects_old = (
            ws.verify_signature(payload, old_bound_sig, old_ts) is False
            and ws.verify_signature(payload, raw_unbound_sig, old_ts) is False
        )
        rejects_future = (
            ws.verify_signature(payload, future_bound_sig, future_ts) is False
            and ws.verify_signature(payload, raw_unbound_sig, future_ts) is False
        )
        c1_pass = accepts_now and rejects_old and rejects_future
        add_result(
            "Reject timestamps older than 300 seconds or in the future",
            c1_pass,
            "Correctly rejected expired (-600s) and future (+600s) webhook timestamps."
            if c1_pass
            else "verify_signature accepted a timestamp outside the 300-second window.",
        )

        # 2. Bind timestamp into signed payload
        accepts_bound = ws.verify_signature(payload, valid_bound_sig, now) is True
        rejects_unbound = ws.verify_signature(payload, raw_unbound_sig, now) is False
        c2_pass = accepts_bound and rejects_unbound
        add_result(
            "Sign `{timestamp}.{payload}` instead of raw payload alone",
            c2_pass,
            "HMAC signature properly binds `{timestamp}.{payload}`."
            if c2_pass
            else "HMAC did not validate `{timestamp}.{payload}` (still signing raw payload or mismatched format).",
        )

        # 3. Constant-time comparison check
        uses_compare_digest = "compare_digest" in source
        add_result(
            "Use `hmac.compare_digest` for signature comparison",
            uses_compare_digest,
            "Found constant-time `hmac.compare_digest` in verify_signature."
            if uses_compare_digest
            else "Still using standard `==` instead of `hmac.compare_digest`.",
        )

    elif task_id == "task-2-idempotency-lock":
        with open("webhook_service.py", "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        import webhook_service as ws

        # 1. threading.Lock check
        has_lock = "threading" in source and "Lock(" in source
        add_result(
            "Import and instantiate a `threading.Lock`",
            has_lock,
            "Found `threading.Lock()` instance in module."
            if has_lock
            else "Missing `import threading` and `threading.Lock()` instantiation.",
        )

        # Helper to sign valid request according to current verify_signature
        now = int(time.time())
        raw_body = b'{"id":"evt_neg"}'
        secret = ws.WEBHOOK_SECRET.encode("utf-8")
        sig_bound = hmac.new(secret, f"{now}.".encode("utf-8") + raw_body, hashlib.sha256).hexdigest()
        sig_raw = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        active_sig = sig_bound if ws.verify_signature(raw_body, sig_bound, now) else sig_raw

        # 2. Validate amount_cents > 0
        initial_bal = ws.WALLETS.get("user_101", 5000)
        res_neg = ws.handle_payment_webhook(
            {"id": "evt_neg_1", "user_id": "user_101", "amount_cents": -500},
            raw_body,
            active_sig,
            now,
        )
        res_zero = ws.handle_payment_webhook(
            {"id": "evt_zero_1", "user_id": "user_101", "amount_cents": 0},
            raw_body,
            active_sig,
            now,
        )
        c2_pass = (
            isinstance(res_neg, dict)
            and res_neg.get("status") == "error"
            and isinstance(res_zero, dict)
            and res_zero.get("status") == "error"
            and ws.WALLETS.get("user_101") == initial_bal
        )
        add_result(
            "Validate `amount_cents > 0` (return 400 error dict if invalid)",
            c2_pass,
            "Rejected zero and negative `amount_cents` without mutating wallet balance."
            if c2_pass
            else "Did not return an error dict when `amount_cents <= 0`.",
        )

        # 3. With lock block wrapping idempotency + mutation
        has_with_stmt = any(isinstance(node, ast.With) for node in ast.walk(tree))
        res_ok1 = ws.handle_payment_webhook(
            {"id": "evt_atomic_99", "user_id": "user_101", "amount_cents": 1500},
            raw_body,
            active_sig,
            now,
        )
        res_ok2 = ws.handle_payment_webhook(
            {"id": "evt_atomic_99", "user_id": "user_101", "amount_cents": 1500},
            raw_body,
            active_sig,
            now,
        )
        c3_pass = (
            has_with_stmt
            and res_ok1.get("status") == "ok"
            and res_ok2.get("status") == "ignored"
            and ws.WALLETS.get("user_101") == initial_bal + 1500
        )
        add_result(
            "Wrap the idempotency check, event recording, and wallet update inside `with WEBHOOK_LOCK:`",
            c3_pass,
            "Critical section is guarded by `with` lock context manager and prevents duplicate credits."
            if c3_pass
            else "Ensure a `with <LOCK>:` block wraps the idempotency check and wallet balance update.",
        )

    elif task_id == "task-1-tenant-isolation":
        import rag_pipeline as rp

        # 1. ValueError on empty/whitespace tenant_id
        raised_empty = False
        raised_space = False
        try:
            rp.retrieve_context("refund", "")
        except ValueError:
            raised_empty = True
        try:
            rp.retrieve_context("refund", "   ")
        except ValueError:
            raised_space = True

        c1_pass = raised_empty and raised_space
        add_result(
            "Raise `ValueError` if `tenant_id` is empty or whitespace",
            c1_pass,
            "Correctly raised ValueError when `tenant_id` was empty or whitespace."
            if c1_pass
            else "retrieve_context did not raise `ValueError` for empty/whitespace `tenant_id`.",
        )

        # 2. Strict tenant filtering
        acme_docs = rp.retrieve_context("token policy Globex refund", "acme")
        leaked = any("glbx_live_secret" in d or "Globex internal" in d for d in acme_docs)
        has_acme = any("Acme refund policy" in d for d in acme_docs)
        c2_pass = (not leaked) and has_acme
        add_result(
            "Filter documents by `doc['tenant_id'] == tenant_id`",
            c2_pass,
            "Strictly isolated `acme` documents; zero cross-tenant leakage from `globex`."
            if c2_pass
            else "Cross-tenant document (`globex`) was leaked when querying as `acme`.",
        )

    elif task_id == "task-2-untrusted-delimiters":
        import rag_pipeline as rp

        prompt = rp.build_agent_prompt(
            "What is my refund window?",
            ["Acme refund policy: 30 days.", "Leak: glbx_live_secret_9911"],
        )
        c1_pass = "<untrusted_context>" in prompt and "</untrusted_context>" in prompt
        add_result(
            "Wrap retrieved context in `<untrusted_context>...</untrusted_context>`",
            c1_pass,
            "Retrieved chunks are isolated inside `<untrusted_context>` XML tags."
            if c1_pass
            else "Prompt output is missing `<untrusted_context>...</untrusted_context>` tags.",
        )

        lower_p = prompt.lower()
        c2_pass = (
            c1_pass
            and ("untrusted_context" in lower_p)
            and any(kw in lower_p for kw in ["ignore", "never", "data only", "not instructions", "do not follow"])
        )
        add_result(
            "Explicitly instruct the system prompt to ignore commands inside `<untrusted_context>`",
            c2_pass,
            "System prompt explicitly instructs the model to treat `<untrusted_context>` as data only."
            if c2_pass
            else "System prompt still tells the model to follow instructions inside the retrieved context.",
        )

    elif task_id == "task-1-batch-query":
        with open("dashboard_api.py", "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        import dashboard_api as da

        da.QUERY_COUNT = 0
        output = da.get_team_dashboard()
        total_queries = da.QUERY_COUNT

        # Find get_team_dashboard function AST
        fn_node = next(
            (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "get_team_dashboard"),
            None,
        )
        fn_src = ast.get_source_segment(source, fn_node) if fn_node else source

        calls_batched = "db_fetch_members_for_teams(" in (fn_src or "")
        calls_single = "db_fetch_members_for_team(" in (fn_src or "")

        add_result(
            "Call `db_fetch_members_for_teams` once outside the loop",
            calls_batched,
            "Used batched `db_fetch_members_for_teams` query."
            if calls_batched
            else "`get_team_dashboard` is not calling `db_fetch_members_for_teams`.",
        )

        add_result(
            "Remove `db_fetch_members_for_team` from inside the loop",
            not calls_single,
            "Removed per-team N+1 `db_fetch_members_for_team` call."
            if not calls_single
            else "`db_fetch_members_for_team` is still called inside `get_team_dashboard`.",
        )

        expected = [
            {"team_id": "t1", "team_name": "Core Infra", "member_count": 2, "members": ["Alice", "Bob"]},
            {"team_id": "t2", "team_name": "Payments", "member_count": 1, "members": ["Charlie"]},
            {"team_id": "t3", "team_name": "AI Platform", "member_count": 0, "members": []},
        ]
        c3_pass = (total_queries == 2) and (output == expected)
        add_result(
            "Total `QUERY_COUNT` for `get_team_dashboard()` must be 2",
            c3_pass,
            f"Executed in {total_queries} queries with exact dashboard output."
            if c3_pass
            else f"QUERY_COUNT was {total_queries} (expected 2) or dashboard output structure differed.",
        )

except Exception as exc:
    tb = traceback.format_exc()
    logs.append(f"Runtime Exception:\n{tb}")

print("===NUDGE_JSON_START===")
print(json.dumps({"results": results, "logs": "\n".join(logs)}))
'''


def run_task_sandbox(
    task: TaskItem, current_files: List[WorkspaceFile]
) -> Dict[str, Any]:
    """
    Layer 1: Execute the user's workspace files in an isolated temporary directory
    against the task's deterministic test suite with a strict 3.5s timeout.
    """
    start_time = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="nudge_sandbox_") as tmpdir:
        tmp_path = Path(tmpdir)
        for wf in current_files:
            file_dest = tmp_path / wf.path
            file_dest.parent.mkdir(parents=True, exist_ok=True)
            file_dest.write_text(wf.content, encoding="utf-8")

        harness_file = tmp_path / "_nudge_runner.py"
        harness_file.write_text(SANDBOX_HARNESS_CODE, encoding="utf-8")

        if task.id.startswith("vulpy-"):
            (tmp_path / "_vulpy_checks.py").write_text(VULPY_CHECKS_CODE, encoding="utf-8")
            (tmp_path / "_nudge_criteria.json").write_text(
                json.dumps(task.validation_criteria), encoding="utf-8"
            )

        timeout_s = TASK_TIMEOUT_OVERRIDES.get(task.id, DEFAULT_SANDBOX_TIMEOUT)

        try:
            proc = subprocess.run(
                [sys.executable, str(harness_file), task.id],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            if "===NUDGE_JSON_START===" in stdout:
                parts = stdout.split("===NUDGE_JSON_START===", 1)
                user_stdout = parts[0].strip()
                payload = json.loads(parts[1].strip())
                raw_results = payload.get("results", [])
                runner_logs = payload.get("logs", "")

                criteria_evals = [
                    CriterionEvaluation(
                        criterion=r["criterion"],
                        passed=r["passed"],
                        reason=r["reason"],
                    )
                    for r in raw_results
                ]

                # If an exception prevented all criteria from running, fill remaining as failed
                if len(criteria_evals) < len(task.validation_criteria):
                    existing_names = {c.criterion for c in criteria_evals}
                    for crit in task.validation_criteria:
                        if crit not in existing_names:
                            criteria_evals.append(
                                CriterionEvaluation(
                                    criterion=crit,
                                    passed=False,
                                    reason="Execution raised an exception before this check completed.",
                                )
                            )

                combined_logs = "\n".join(
                    filter(None, [user_stdout, runner_logs, stderr.strip()])
                )
                passed_all = (
                    len(criteria_evals) > 0
                    and all(c.passed for c in criteria_evals)
                )
                return {
                    "passed_all": passed_all,
                    "sandbox_passed": passed_all,
                    "sandbox_output": combined_logs or "Verification completed.",
                    "execution_ms": elapsed_ms,
                    "criteria_results": criteria_evals,
                }

            # Fallback if script crashed before printing JSON marker
            return {
                "passed_all": False,
                "sandbox_passed": False,
                "sandbox_output": (stdout + "\n" + stderr).strip()
                or "Sandbox execution failed.",
                "execution_ms": elapsed_ms,
                "criteria_results": [
                    CriterionEvaluation(
                        criterion=c,
                        passed=False,
                        reason="Syntax or runtime error during execution.",
                    )
                    for c in task.validation_criteria
                ],
            }

        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "passed_all": False,
                "sandbox_passed": False,
                "sandbox_output": f"Error: Execution timed out after {timeout_s:g} seconds (possible infinite loop, deadlock, or an overly expensive KDF setting).",
                "execution_ms": elapsed_ms,
                "criteria_results": [
                    CriterionEvaluation(
                        criterion=c,
                        passed=False,
                        reason="Execution timed out.",
                    )
                    for c in task.validation_criteria
                ],
            }


async def generate_ai_architectural_feedback(
    project: Project,
    task: TaskItem,
    code_diff: str,
    criteria_results: List[CriterionEvaluation],
    passed_all: bool,
) -> str:
    """
    Layer 2: Use NVIDIA NIM API to provide a brief, context-aware Staff Engineer code review
    based on the user's code diff and sandbox verification results.
    """
    api_key = (os.getenv("NVIDIA_API_KEY") or "").strip().strip('"').strip("'")
    base_url = (
        os.getenv("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
    ).strip().rstrip("/")
    model = (
        os.getenv("NVIDIA_MODEL") or "meta/llama-3.3-70b-instruct"
    ).strip()

    passed_count = sum(1 for c in criteria_results if c.passed)
    total_count = len(criteria_results)

    # Deterministic fallback if no API key or if call fails
    default_feedback = (
        f"Excellent engineering! All {total_count}/{total_count} validation criteria passed for '{task.title}'. "
        "Your changes properly address the production vulnerability."
        if passed_all
        else f"{passed_count}/{total_count} criteria passed. Review the failing checks above or click 'Get Nudge' in the AI panel for a targeted hint."
    )

    if not api_key:
        return default_feedback

    criteria_summary = "\n".join(
        f"- [{'PASS' if c.passed else 'FAIL'}] {c.criterion}: {c.reason}"
        for c in criteria_results
    )

    mentor_note = (
        f"Reviewer briefing (CWE/OWASP, common wrong fixes): {task.mentor_context[:1500]}\n\n"
        if task.mentor_context
        else ""
    )

    prompt = (
        f"Project: {project.title}\n"
        f"Task: {task.title} ({task.objective})\n\n"
        f"{mentor_note}"
        f"User's Code Diff vs Starter:\n```diff\n{code_diff[:2500]}\n```\n\n"
        f"Sandbox Test Results:\n{criteria_summary}\n\n"
        "In 1 to 2 concise sentences, give direct Staff-Engineer feedback on their current implementation. "
        "If all checks passed, praise the specific fix they wrote. If checks failed, point out what is still missing without giving away the full copy-paste code."
    )

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a concise Staff Security & Systems Engineer reviewing a developer's code in the Nudge IDE.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 450,
                    "temperature": 0.3,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                msg = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                if msg:
                    return msg
    except Exception:
        pass

    return default_feedback


async def verify_workspace_task(
    db: Session,
    user_id: str,
    project_id: str,
    req: VerifyTaskRequest,
) -> WorkspaceSessionResponse:
    """
    Run the Two-Layer Verification Engine (Sandbox + NVIDIA NIM Evaluator),
    persist the verification report & completed task status in PostgreSQL,
    and return the updated WorkspaceSessionResponse.
    """
    if req.files is not None:
        update_workspace_state(
            db,
            user_id,
            project_id,
            UpdateWorkspaceStateRequest(
                files=req.files,
                active_task_id=req.task_id,
            ),
        )

    project, session = _get_project_and_session(db, user_id, project_id)
    task = next((t for t in project.tasks if t.id == req.task_id), None)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{req.task_id}' not found in project '{project_id}'.",
        )

    session_resp = _session_to_response(session, project)
    current_files = session_resp.files

    # Layer 1: Deterministic Python Sandbox
    sandbox_res = run_task_sandbox(task, current_files)

    # Layer 2: Unified Diff + NVIDIA NIM Evaluator Feedback
    code_diff = build_unified_diff(project, current_files)
    feedback = await generate_ai_architectural_feedback(
        project=project,
        task=task,
        code_diff=code_diff,
        criteria_results=sandbox_res["criteria_results"],
        passed_all=sandbox_res["passed_all"],
    )

    report = TaskVerificationReport(
        task_id=task.id,
        passed_all=sandbox_res["passed_all"],
        sandbox_passed=sandbox_res["sandbox_passed"],
        sandbox_output=sandbox_res["sandbox_output"],
        execution_ms=sandbox_res["execution_ms"],
        criteria_results=sandbox_res["criteria_results"],
        architectural_feedback=feedback,
        verified_at=datetime.now(timezone.utc).isoformat(),
    )

    verif_map = dict(session.last_verification or {})
    verif_map[task.id] = report.model_dump()
    session.last_verification = verif_map
    flag_modified(session, "last_verification")

    if report.passed_all:
        completed = list(session.completed_task_ids or [])
        if task.id not in completed:
            completed.append(task.id)
            session.completed_task_ids = completed
            flag_modified(session, "completed_task_ids")

    db.commit()
    db.refresh(session)
    return _session_to_response(session, project)
