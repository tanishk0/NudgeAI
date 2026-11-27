"""Ready-to-use package plumbing; learners implement agent behavior only."""
from app.models import ProjectFile
from app.mini_swe_layout import PACKAGE, GUIDE, FIXTURE


def boilerplate_files(root):
    contents = {
        'README.md': '''# Build mini-swe-agent

This workspace follows SWE-agent/mini-swe-agent's Python package layout at
commit 04d809ceab9df28f9adaed044884180159172930. It is a focused Nudge teaching
adaptation, not a verbatim copy of the full upstream implementation.

Implement the 39 tasks in their real component files:
- src/minisweagent/models/litellm_model.py: LitellmModel
- src/minisweagent/agents/default.py: DefaultAgent and the coding loop
- src/minisweagent/environments/local.py and docker.py: execution boundaries
- src/minisweagent/models/utils/actions_toolcall.py and retry.py: model tools
- src/minisweagent/utils/serialize.py: memory and trajectories
- src/minisweagent/run/: entry points and the inspector
- tests/: checks and the disposable repair fixture

Nudge supplies packaging, imports, configuration, and the execution runtime.
No project initialization or boilerplate setup task is required.
See docs/index.md for the learning workflow. The Run button opens the inspector.

Upstream: https://github.com/SWE-agent/mini-swe-agent
MIT attribution is in LICENSE.md.
''',
        'pyproject.toml': '''[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "mini-swe-agent"
version = "0.1.0"
description = "Nudge learning adaptation of mini-swe-agent"
requires-python = ">=3.12"
dependencies = ["litellm>=1.75.5,!=1.82.7,!=1.82.8", "tenacity", "Flask"]

[project.scripts]
mini = "minisweagent.run.mini:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
minisweagent = ["config/*.yaml"]
''',
        '.gitignore': '.venv/\n__pycache__/\n*.pyc\n.env\nruns/\n',
        GUIDE: (root / 'starter/COURSE.md').read_text(encoding='utf-8') + '''

## Package layout

Code lives in src/minisweagent, matching the upstream repository's component
folders. The model adapter is LitellmModel; the coordinator is DefaultAgent.
Imports use minisweagent.*. Nudge configures the src directory automatically.
The inspector lives in run/utilities/inspector.py; the repair fixture is under
tests/test_data/buggy_repository. Supplied test files demonstrate the public
interfaces; Check task also uses trusted acceptance checks outside this tree.
''',
        'LICENSE.md': (root / 'upstream/LICENSE.md').read_text(encoding='utf-8'),
        PACKAGE + '__init__.py': '"""A learning edition of the mini-swe-agent package."""\n__version__ = "0.1.0"\n',
        PACKAGE + '__main__.py': 'from minisweagent.run.mini import main\n\nif __name__ == "__main__":\n    main()\n',
        PACKAGE + 'py.typed': '',
        PACKAGE + 'config/default.yaml': '''# Prompt reference for the task-template exercise.
system_template: "Inspect the repository, repair the bug, and verify with tests."
instance_template: "Repository: {repository}\\nTask: {task}"
step_limit: 10
command_timeout: 2
''',
        PACKAGE + 'run/mini.py': '''"""An already-wired CLI; use an exported trusted setup for live providers."""
import argparse
import json
from minisweagent.models.litellm_model import LitellmModel
from minisweagent.agents.default import run_agent
from minisweagent.environments.docker import DockerEnvironment


def main():
    parser = argparse.ArgumentParser(description="Run the mini-swe learning agent")
    parser.add_argument("--task", required=True)
    parser.add_argument("--model", required=True, help="LiteLLM provider/model name")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    environment = DockerEnvironment()
    try:
        environment.start(args.repo)
        environment.provision()
        def runner(command, cwd, timeout=2):
            return environment.execute(command, timeout=timeout)
        result = run_agent(LitellmModel(args.model), args.task, args.repo, runner)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        environment.close()


if __name__ == "__main__":
    main()
''',
        'tests/models/test_litellm_model.py': '''import unittest
from minisweagent.models.litellm_model import LitellmModel

class ModelTests(unittest.TestCase):
    def test_injected_completion(self):
        def complete(**kwargs):
            return {"choices": [{"message": {"role": "assistant", "content": "hello"}}]}
        self.assertEqual(LitellmModel("test/model", complete).query([])["content"], "hello")
''',
        'tests/agents/test_default.py': '''import unittest
from minisweagent.agents.default import DefaultAgent

class AgentTests(unittest.TestCase):
    def test_independent_history(self):
        first, second = DefaultAgent(object()), DefaultAgent(object())
        first.messages.append({"role": "user", "content": "one"})
        self.assertEqual(len(second.messages), 1)
''',
        'tests/environments/test_local.py': '''import tempfile
import unittest
from minisweagent.environments.local import execute

class EnvironmentTests(unittest.TestCase):
    def test_captured_output(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(execute("printf hello", directory)["output"], "hello")
''',
        'tests/utils/test_serialize.py': '''import unittest
from minisweagent.utils.serialize import token_usage

class MemoryTests(unittest.TestCase):
    def test_usage(self):
        self.assertEqual(token_usage({"usage": {"prompt_tokens": 2, "completion_tokens": 3}})["total"], 5)
''',
    }
    for directory in ['agents', 'agents/utils', 'models', 'models/utils', 'environments', 'utils', 'run', 'run/utilities', 'config']:
        contents[PACKAGE + directory + '/__init__.py'] = '"""mini-swe-agent component package."""\n'
    for directory in ['tests', 'tests/models', 'tests/agents', 'tests/environments', 'tests/utils', 'tests/test_data']:
        contents[directory + '/__init__.py'] = ''
    for name in ['calculator.py', 'test_calculator.py']:
        contents[FIXTURE + '/' + name] = (root / 'starter/buggy_repository' / name).read_text(encoding='utf-8')
    return [ProjectFile(path=path, language='python' if path.endswith('.py') else 'toml' if path.endswith('.toml') else 'yaml' if path.endswith('.yaml') else 'markdown' if path.endswith('.md') else 'plaintext', content=content, read_only=not path.startswith(FIXTURE + '/')) for path, content in sorted(contents.items())]
