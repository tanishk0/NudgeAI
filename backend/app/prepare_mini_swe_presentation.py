"""Instructor-only rehearsal export; never exposed through the learner API."""
import zipfile
from pathlib import Path
from app.projects_mini_swe import MINI_SWE_PROJECT, ROOT


def export_rehearsal(output=None):
    target = Path(output) if output else ROOT.parent.parent / ".rehearsal" / "mini-swe-agent-completed.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    from app.mini_swe_layout import repository_solutions
    packaged = repository_solutions(ROOT)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in MINI_SWE_PROJECT.starter_files:
            solution = ROOT / "solutions" / file.path
            content = packaged.get(file.path, solution.read_text(encoding="utf-8") if solution.is_file() else file.content)
            archive.writestr(file.path, content)
    return target.resolve()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export the completed mini-swe-agent teaching edition for instructor rehearsal.")
    parser.add_argument("--output", help="ZIP output path")
    args = parser.parse_args()
    print(export_rehearsal(args.output))
    print("Contains instructor reference implementations. Do not distribute as an unfinished learner workspace.")
