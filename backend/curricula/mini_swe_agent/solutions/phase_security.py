"""Phase 7: enforce structured policies outside the model's prompts."""
from pathlib import Path


def allowed_path(root, candidate):
    root = Path(root).resolve()
    supplied = Path(candidate)
    if supplied.is_absolute():
        raise PermissionError("Use a repository-relative path")
    target = (root / supplied).resolve()
    if not target.is_relative_to(root):
        raise PermissionError("Outside repository")
    if any(part.lower() in {".env", ".git", ".aws", ".ssh"} or part.lower().startswith(".env.") for part in target.relative_to(root).parts):
        raise PermissionError("Sensitive path")
    return target


def safe_environment(source):
    # Explicit values only: inheriting os.environ can leak credentials.
    return {key: source[key] for key in ("PATH", "LANG", "LC_ALL") if key in source}


def authorize_network(destination):
    raise PermissionError("Network is disabled")


def authorize(action, approve):
    kind = action.get("kind")
    if kind == "network":
        authorize_network(action.get("destination"))
    if kind not in {"read", "write", "bash", "delete"}:
        raise PermissionError("Unknown action")
    if kind in {"bash", "delete"} and approve(action) is not True:
        raise PermissionError("Approval required")
    return True


def inspect_changes(cwd, runner):
    result = runner(["git", "diff", "--no-ext-diff", "--no-textconv", "--", "."], cwd=cwd, capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout
