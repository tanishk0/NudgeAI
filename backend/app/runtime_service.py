"""Local isolated execution. Learner code is never executed by the API interpreter."""
import json
import base64
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
import httpx
from fastapi import HTTPException
from app.file_policy import normalize_path, validate_files

IMAGE = os.getenv("NUDGE_RUNTIME_IMAGE", "nudge-runtime:local")
MAX_LOG_BYTES = 32_000
_slots = threading.BoundedSemaphore(3)
_leases = {}
_lock = threading.RLock()

def _docker(*args, timeout=15, input_data=None):
    if not shutil.which("docker"):
        raise HTTPException(503, "Code execution needs Docker Desktop. Install it, start the engine, and build the Nudge runtime image.")
    try:
        result = subprocess.run(["docker", *args], input=input_data, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(503, "The isolated runtime is unavailable. Check that Docker Desktop is running.") from exc
    if result.returncode:
        logger = logging.getLogger("nudge.runtime")
        (logger.debug if args[0] == "exec" else logger.warning)("Docker %s failed: %s", args[0], result.stderr[-1200:])
        # Do not expose host paths or daemon diagnostics to learners.
        raise HTTPException(503, "Cannot start the isolated runtime. Start Docker Desktop and run: docker build -t nudge-runtime:local backend/runtime")
    return (result.stdout + (result.stderr if args and args[0] == "logs" else "")).strip()

def _base(name):
    return ["--name", name, "--label", "app=nudge", "--read-only", "--user", "1000:1000",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "64",
        "--memory", "192m", "--cpus", "0.5", "--ulimit", "fsize=4194304:4194304",
        "--tmpfs", "/work:rw,nosuid,nodev,size=16m,uid=1000,gid=1000",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m,uid=1000,gid=1000",
        "--log-driver", "local", "--log-opt", "max-size=1m", "--log-opt", "max-file=1", "--log-opt", "compress=false",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "PYTHONUNBUFFERED=1", "--env", "PYTHONPATH=/work/src", "--workdir", "/work"]

def _materialize(directory, files):
    validate_files(files)
    Path(directory).chmod(0o755)  # The non-root Linux container must be able to traverse its read-only input mount.
    for file in files:
        target = Path(directory) / normalize_path(file.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file.content, encoding="utf-8")

def _remove(name):
    try:
        _docker("rm", "-f", name)
    except HTTPException:
        pass

def execute_python(files, entrypoint, args=(), timeout=10, trusted_files=None):
    if not _slots.acquire(blocking=False):
        raise HTTPException(429, "All execution slots are busy. Please retry shortly.")
    name = "nudge-check-" + uuid.uuid4().hex
    try:
        with tempfile.TemporaryDirectory(prefix="nudge-input-") as directory:
            _materialize(directory, files)
            for path, content in (trusted_files or {}).items():
                (Path(directory) / path).write_text(content, encoding="utf-8")
            command = ["run", "-d", *_base(name), "--network", "none", "--mount",
                f"type=bind,source={directory},target=/input,readonly", IMAGE,
                "sh", "-c", 'cp -R /input/. /work/ && limit="$1" && shift && exec timeout --signal=TERM --kill-after=1s "$limit" python "$@"', "nudge", f"{timeout:g}s", entrypoint, *args]
            try:
                _docker(*command)
                # Python's execution budget starts after provisioning. Allow
                # separate time for Docker Desktop's control plane and copying.
                code = int(_docker("wait", name, timeout=timeout + 15))
                output = _docker("logs", name)[-MAX_LOG_BYTES:]
                if code == 124:
                    raise TimeoutError(f"Execution exceeded {timeout:g} seconds.\n{output[-8000:]}")
                if code == 137:
                    raise TimeoutError(f"Execution was stopped by a time or memory limit.\n{output[-8000:]}")
                return {"stdout": output, "stderr": "", "returncode": code}
            except HTTPException as exc:
                if exc.__cause__ and isinstance(exc.__cause__, subprocess.TimeoutExpired):
                    raise TimeoutError(f"Execution exceeded {timeout:g} seconds.") from exc
                raise
            finally:
                _remove(name)
    finally:
        _slots.release()

DEMOS = {
    "flawed-ai-payment-webhook": "import webhook_service as app\nprint('Payment service loaded. Current wallets:', app.WALLETS)\nprint('Use Check task to exercise signature validation and duplicate delivery.')",
    "rag-prompt-injection-firewall": "import rag_pipeline as app\nprint('Acme retrieval:', app.retrieve_context('refund token', 'acme'))\nprint(app.build_agent_prompt('What is my refund policy?', app.retrieve_context('refund', 'acme')))",
    "n-plus-one-connection-pool-collapse": "import dashboard_api as app\nimport json\napp.QUERY_COUNT=0\nprint(json.dumps(app.get_team_dashboard(), indent=2))\nprint('Database queries:', app.QUERY_COUNT)",
}

def run_project(project, session_id, revision, files):
    if project.runtime.get("mode") != "web":
        start = time.monotonic()
        result = execute_python(files, "_nudge_demo.py", trusted_files={"_nudge_demo.py": DEMOS.get(project.id, "print('Use Check task to run this exercise.')")})
        return dict(status="finished", revision=revision, output=result["stdout"], exit_code=result["returncode"], execution_ms=int((time.monotonic()-start)*1000))
    stop_project(session_id)
    name = "nudge-preview-" + uuid.uuid4().hex
    directory = tempfile.TemporaryDirectory(prefix="nudge-preview-")
    try:
        _materialize(directory.name, files)
        # Preview traffic uses docker exec, so the container needs no network interface or published port.
        with _lock:
            if len(_leases) >= 3:
                raise HTTPException(429, "All preview slots are busy. Stop an existing preview first.")
            _leases[session_id] = dict(name=name, directory=directory, revision=revision, expires=time.monotonic()+600)
        entrypoint = project.runtime["entrypoint"].removesuffix(".py")
        if entrypoint.startswith('src/'):
            entrypoint = entrypoint.removeprefix('src/').replace('/', '.')
        _docker("run", "-d", *_base(name), "--network", "none", "--mount",
            f"type=bind,source={directory.name},target=/input,readonly", IMAGE, "sh", "-c",
            'cp -R /input/. /work/ && exec python -m flask --app "$1" run --host=0.0.0.0 --port=5000', "nudge", entrypoint)
        timer = threading.Timer(600, lambda: _expire(session_id, name))
        timer.daemon = True
        timer.start()
        for _ in range(30):
            try:
                response = preview_response(session_id, "GET", project.runtime.get("path","/"))
                if response["status"] < 500:
                    return dict(status="running", revision=revision, output="Application ready. Preview stops automatically after 10 minutes.", exit_code=None,
                        preview_path=project.runtime.get("path","/"))
            except (HTTPException, ValueError):
                pass
            time.sleep(0.2)
        logs = _docker("logs", name)[-MAX_LOG_BYTES:]
        stop_project(session_id)
        return dict(status="failed", revision=revision, output=logs or "The application did not become ready.", exit_code=1)
    except Exception:
        stop_project(session_id)
        directory.cleanup()
        raise

def _expire(session_id,name):
    with _lock:
        lease=_leases.get(session_id)
        if lease and lease["name"]==name:
            stop_project(session_id)

def stop_project(session_id):
    with _lock:
        lease = _leases.pop(session_id, None)
    if lease:
        _remove(lease["name"])
        lease["directory"].cleanup()

def _lease(session_id):
    with _lock:
        lease = _leases.get(session_id)
        if not lease or lease["expires"] < time.monotonic():
            raise HTTPException(410, "Preview expired. Run the application again.")
        return lease


PREVIEW_PROXY = r'''
import base64, http.client, json, sys
request = json.load(sys.stdin)
connection = http.client.HTTPConnection("127.0.0.1", 5000, timeout=5)
connection.request(request["method"], request["path"], body=base64.b64decode(request["body"]),
    headers={"Content-Type": request["content_type"], "Cookie": request.get("cookie", "")})
response = connection.getresponse()
body = response.read(2 * 1024 * 1024 + 1)
if len(body) > 2 * 1024 * 1024:
    raise ValueError("Preview response exceeds 2 MB")
print(json.dumps({"status": response.status, "headers": response.getheaders(), "body": base64.b64encode(body).decode()}))
connection.close()
'''


def preview_response(session_id, method, path, body=b"", content_type="application/octet-stream"):
    lease = _lease(session_id)
    # The protocol script is author-controlled; only request data is passed over stdin.
    payload = json.dumps(dict(method=method, path=path, body=base64.b64encode(body).decode(),
        content_type=content_type, cookie=lease.get("cookie", "")))
    raw = _docker("exec", "-i", lease["name"], "python", "-c", PREVIEW_PROXY, timeout=8, input_data=payload)
    result = json.loads(raw)
    from http.cookies import SimpleCookie
    cookies = SimpleCookie()
    cookies.load(lease.get("cookie", ""))
    for name, value in result["headers"]:
        if name.lower() == "set-cookie":
            cookies.load(value)
    lease["cookie"] = "; ".join(f"{key}={value.value}" for key,value in cookies.items())
    result["body"] = base64.b64decode(result["body"])
    return result

def stop_all():
    for session_id in list(_leases):
        stop_project(session_id)
