"""This shell executor is for Nudge's isolated Linux runtime, never its API host."""
import os
import signal
import subprocess

SENTINEL = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"


def execute(command, cwd, timeout=1):
    """One new shell per action; merge stderr, preserve failures and partial output."""
    process = subprocess.Popen(command, shell=True, executable="/bin/bash", cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", start_new_session=True)
    timed_out = False
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
    return {"output": output[-8000:], "returncode": process.returncode, "timed_out": timed_out}


def completion(result):
    """Only a successful command with the marker as its first line can submit."""
    lines = result["output"].splitlines(keepends=True)
    if not result.get("timed_out") and result["returncode"] == 0 and lines and lines[0].strip() == SENTINEL:
        return "".join(lines[1:])
    return None
