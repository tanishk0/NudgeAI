"""Phase 5: bounded provider retries and multi-dimensional budgets."""
import math
import time
import subprocess


class TransientAPIError(Exception):
    pass


class LimitsExceeded(Exception):
    pass


class MalformedToolCall(ValueError):
    pass


def classify_error(error):
    if isinstance(error, TransientAPIError):
        return "retry"
    if isinstance(error, MalformedToolCall):
        return "correct"
    if isinstance(error, LimitsExceeded):
        return "stop"
    return "raise"


def backoff(attempt):
    if type(attempt) is not int or attempt < 1:
        raise ValueError("attempt must be a positive integer")
    return 2 ** min(attempt - 1, 3)


def timed_command(command, cwd, runner, timeout=2):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    try:
        return runner(command, cwd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return {"output": output[-8000:], "returncode": -1, "timed_out": True}


def retry_api(operation, attempts=3, sleep=time.sleep):
    from tenacity import Retrying, stop_after_attempt, wait_exponential, retry_if_exception_type
    if attempts < 1:
        raise ValueError("attempts must be positive")
    retryer = Retrying(stop=stop_after_attempt(attempts), wait=wait_exponential(multiplier=1, max=8), retry=retry_if_exception_type(TransientAPIError), sleep=sleep, reraise=True)
    return retryer(operation)


def remaining_budget(usage, limits):
    for key in ("steps", "tokens", "cost", "seconds"):
        used, limit = usage[key], limits[key]
        if isinstance(used, bool) or isinstance(limit, bool) or not isinstance(used, (int, float)) or not isinstance(limit, (int, float)) or not math.isfinite(used) or not math.isfinite(limit) or used < 0 or limit <= 0:
            raise ValueError("Invalid budget")
        if used >= limit:
            raise LimitsExceeded(key)
    return True


def safe_tool(call, cwd, runner):
    from phase_tools import parse_tool
    try:
        command = parse_tool(call)
    except ValueError as exc:
        raise MalformedToolCall(str(exc)) from exc
    return runner(command, cwd, timeout=2)
