"""Reproducible project setup, with an injectable virtual-environment builder."""
from pathlib import Path
import venv


def initialize_project(root, builder=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name, text in {"requirements.txt": "litellm\ntenacity\n", ".gitignore": ".venv/\n.env\n"}.items():
        path = root / name
        if not path.exists():
            path.write_text(text, encoding="utf-8")
    (builder or venv.EnvBuilder(with_pip=False)).create(root / ".venv")
    return str(root.resolve())
