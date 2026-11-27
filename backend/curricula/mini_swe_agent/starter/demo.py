"""A reproducible scripted-model experiment, NOT a live LLM response."""
import difflib
import json
import tempfile
from pathlib import Path
from agent import Agent
from model import ScriptedModel
from evaluation import verify_submission

BUGGY = "def add(a, b):\n    return a - b\n"
TEST = "import unittest\nfrom calculator import add\nclass AdditionTests(unittest.TestCase):\n    def test_positive(self): self.assertEqual(add(2, 3), 5)\n    def test_negative(self): self.assertEqual(add(-2, -3), -5)\n"


def responses():
    commands = ["python -m unittest discover -s . -p 'test_*.py'", "cat calculator.py",
        "python -c \"from pathlib import Path; Path('calculator.py').write_text('def add(a, b):\\n    return a + b\\n')\"",
        "python -m unittest discover -s . -p 'test_*.py'",
        "printf 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\\nFixed addition; regression tests pass.\\n'"]
    return [{"content": f"```bash\n{command}\n```", "cost": 0.01} for command in commands]


def run_demo():
    with tempfile.TemporaryDirectory() as cwd:
        root = Path(cwd)
        (root / "calculator.py").write_text(BUGGY)
        (root / "test_calculator.py").write_text(TEST)
        agent = Agent(ScriptedModel(responses()), cwd)
        try:
            result = agent.run("Fix add(a, b), prove it with tests, then submit.", root / "trajectory.json")
            verification = verify_submission(result, cwd)
            return {"mode": "Scripted model — no live LLM or API calls", "result": result,
                "verification": verification, "messages": agent.messages, "calls": agent.n_calls,
                "cost": agent.cost, "diff": "".join(difflib.unified_diff(BUGGY.splitlines(True), (root / "calculator.py").read_text().splitlines(True), fromfile="before/calculator.py", tofile="after/calculator.py"))}
        except Exception as error:
            return {"mode": "Scripted model — no live LLM or API calls", "error": f"{type(error).__name__}: {error}",
                "messages": agent.messages, "calls": agent.n_calls, "cost": agent.cost}


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
