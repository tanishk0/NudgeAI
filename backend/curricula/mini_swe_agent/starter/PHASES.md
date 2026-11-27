# Seven capstone phases

Complete the 16 foundation tasks first, then implement phase_core.py through
phase_security.py. Each phase has a dedicated Learn the concept page in Nudge.

For an exported project, initialize an isolated Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install litellm tenacity
python -m pip freeze > requirements.txt
```

On Windows activate with `.venv/Scripts/Activate.ps1` in PowerShell.
Keep provider credentials in the trusted provider process, outside repository
files and the environment passed to commands. Nudge acceptance checks inject
the provider completion and Docker CLI. No API credits or nested Docker daemon
are required. Tenacity is preinstalled in the learning runtime.

The existing Run preview demonstrates the foundation agent. For the later
phases use Check task to exercise each new adapter. A live-provider or real
Docker trial belongs in a separately configured exported development setup;
the learning sandbox intentionally has no provider keys or Docker socket.

Use buggy_repository/calculator.py and its test for the autonomy phase.
