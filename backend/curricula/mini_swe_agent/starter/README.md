# Build mini-swe-agent: the learning lab

This is an independently authored **teaching edition**, grounded in the real [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) architecture. It is not a checkout of the complete upstream package and does not reproduce its benchmark results.

Read `upstream/source.json` for the immutable commit and original file paths. The unmodified core agent, local environment, protocols, and MIT license are included in `upstream/` for comparison. Do not import these reference files: the full upstream package has additional dependencies and adapters.

## What you build

`model.py → agent.py → parser.py → environment.py → trajectory.py → evaluation.py`

The Flask viewer and experiment fixture are provided. You implement the agent that drives them. Complete the tasks in order; use Check task after each small step. All commands run inside Nudge's isolated Linux runtime. The environment module itself is a command executor, not a security sandbox.

## Your 16 small steps

1. Prepare the practice model.
2. Return its next reply.
3. Start a clean conversation.
4. Prepare the agent and its settings.
5. Read one command from a reply.
6. Run a command and collect its output.
7. Stop commands that take too long.
8. Recognize a finish message.
9. Check the step and cost limits.
10. Count replies and their cost.
11. Connect one complete agent step.
12. Retry unreadable replies.
13. Create a record of the run.
14. Save that record safely.
15. Keep the agent working until it stops.
16. Check that the repair really works.

The editable files contain imports, names, and empty functions. You write the
behavior, including the setup methods. NotImplementedError means a part is still
waiting for you to build it. Pass Check task to unlock the next numbered task.
The supplied web page and repair example let you try your work; they are not
parts you need to rebuild in this course.

## Run and inspect

Choose **Run**, open **Preview**, and select **Run the repair experiment**. Before implementation the viewer explains which piece is missing. After implementation it displays each turn, a real patch, and test evidence. Restart the runtime after editing source; refreshing the preview alone uses the already running code.

The fixture uses scripted model responses, conspicuously labelled in the UI. The learner's code actually executes commands, modifies a temporary repository, runs Python tests, and verifies the result. It makes no live LLM calls and consumes no model credits. Cost units shown in the lab are simulated. Nudge's mentor is a separate service.

## Relationship to upstream

The upstream v2 agent supports richer message formats, multiple adapters, tool-call formats, configuration templates, and more detailed serialization. This course deliberately uses one fenced bash action per turn and a small JSON schema. Provider independence, linear history, stateless execution, limits, exception recovery, and saved evidence are the shared ideas. Atomic trajectory replacement and independent repair verification are course extensions.

## Local export

Install Flask and run `python -m flask --app app run` **inside an isolated Linux container**. Do not run unreviewed agent-generated shell commands on your personal host. The offline fixture does not require upstream's package or provider credentials.

See `PRESENTATION.md` for a rehearsable story and honest answers to likely questions.
