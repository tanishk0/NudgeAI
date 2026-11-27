"""Phase 4: a Docker CLI adapter; checks inject a fake CLI, never a daemon."""
import subprocess
import uuid
from pathlib import Path


def sandbox_options():
    return ["--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "1000:1000", "--memory", "256m", "--cpus", "1", "--pids-limit", "64", "--tmpfs", "/work:rw,uid=1000,gid=1000,size=64m", "--tmpfs", "/tmp:rw,size=32m"]


class DockerEnvironment:
    def __init__(self, image="nudge-runtime:local", cli=None):
        self.image = image
        self.name = "mini-swe-" + uuid.uuid4().hex
        self.cli = cli or subprocess.run
        self.started = False

    def start(self, repository):
        repository = str(Path(repository).resolve())
        args = ["docker", "run", "-d", "--name", self.name, *sandbox_options(), "--mount", f"type=bind,source={repository},target=/input,readonly", "--workdir", "/work", self.image, "sleep", "infinity"]
        try:
            self.cli(args, check=True, capture_output=True, text=True, timeout=15)
            self.started = True
        except Exception:
            self.close()
            raise
        return self

    def provision(self):
        if not self.started:
            raise RuntimeError("Start the container first")
        try:
            self.cli(["docker", "exec", self.name, "sh", "-c", "cp -R /input/. /work/"], check=True, capture_output=True, text=True, timeout=10)
        except Exception:
            self.close()
            raise

    def execute(self, command, timeout=2):
        if not self.started:
            raise RuntimeError("Start the container first")
        try:
            result = self.cli(["docker", "exec", self.name, "/bin/bash", "-lc", command], capture_output=True, text=True, timeout=timeout)
            return {"output": (result.stdout + result.stderr)[-8000:], "returncode": result.returncode, "timed_out": False}
        except subprocess.TimeoutExpired as exc:
            # A timed-out docker exec client does not stop the container command.
            self.close()
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return {"output": output[-8000:], "returncode": -1, "timed_out": True}

    def close(self):
        self.started = False
        self.cli(["docker", "rm", "-f", self.name], capture_output=True, text=True, timeout=10)
