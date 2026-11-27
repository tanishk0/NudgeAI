from environment import execute


def verify_submission(result, cwd):
    """A model's completion claim does not prove the repository is fixed."""
    if result.get("exit_status") != "Submitted":
        return {"verified": False, "output": "Agent did not submit"}
    check = execute("python -m unittest discover -s . -p 'test_*.py'", cwd, timeout=2)
    return {"verified": check["returncode"] == 0 and not check["timed_out"], "output": check["output"]}
