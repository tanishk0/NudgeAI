"""One path and quota policy for storage, execution, and exports."""
import hashlib
import json
import re
from pathlib import PurePosixPath

MAX_FILES = 100
MAX_FILE_BYTES = 256 * 1024
MAX_WORKSPACE_BYTES = 2 * 1024 * 1024


def normalize_path(value: str) -> str:
    path = value.strip().replace("\\", "/")
    parts = path.split("/")
    if (not path or len(path) > 240 or path.startswith("/")
            or any(p in ("", ".", "..") for p in parts)
            or any(ord(c) < 32 for c in path) or re.search(r'[:<>"|?*]', path)):
        raise ValueError("Use a relative file path without empty segments, '..', or reserved characters.")
    for part in parts:
        if (part.lower().startswith(("_nudge", "_vulpy_checks"))
                or part.lower() in {".git", ".env", ".env.local", ".env.production"}
                or part.endswith((".", " "))
                or part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(10)], *[f"LPT{i}" for i in range(10)]}):
            raise ValueError("This file name is reserved by the workspace.")
    return str(PurePosixPath(path))


def validate_files(files):
    if len(files) > MAX_FILES:
        raise ValueError(f"A workspace can contain at most {MAX_FILES} files.")
    seen, total = set(), 0
    for file in files:
        path = normalize_path(file.path)
        if path.casefold() in seen:
            raise ValueError(f"Duplicate file path: {path}")
        if any(path.casefold().startswith(p + "/") or p.startswith(path.casefold() + "/") for p in seen):
            raise ValueError("A file cannot also be a directory.")
        seen.add(path.casefold())
        size = len(file.content.encode("utf-8"))
        if size > MAX_FILE_BYTES:
            raise ValueError(f"{path} exceeds the 256 KB file limit.")
        total += size
    if total > MAX_WORKSPACE_BYTES:
        raise ValueError("This workspace exceeds the 2 MB limit.")
    return files


def files_hash(files) -> str:
    entries = sorted((f.path, f.content) for f in files)
    return hashlib.sha256(json.dumps(entries, ensure_ascii=False).encode()).hexdigest()
