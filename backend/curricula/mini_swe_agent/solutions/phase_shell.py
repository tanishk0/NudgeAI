"""Bash execution is allowed only inside the existing isolated Linux runner."""
import os
import signal
import subprocess


def execute(command, cwd, timeout=2):
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


def normalize_result(result):
    if not isinstance(result.get("output"), str) or type(result.get("returncode")) is not int or type(result.get("timed_out")) is not bool:
        raise ValueError("Invalid command observation")
    return {"output": result["output"][-8000:], "returncode": result["returncode"], "timed_out": result["timed_out"]}
