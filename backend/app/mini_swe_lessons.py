"""Plain-language instructions for the mini-swe-agent learning path."""
LESSONS = {
    'model': ('Return the next practice reply', 'Let the agent ask for one reply at a time.',
        'In query(messages), save a separate copy of the conversation in self.calls. Return and remove the first item in self.responses. If no replies remain, raise RuntimeError. Changing the original conversation afterward must not change the saved copy. Use copy.deepcopy for a copy of nested lists and dictionaries. These are practice replies, not answers from a live AI service.'),
    'history': ('Give the agent its first instructions', 'Start each task with a clean conversation.',
        'In initial_messages(task), reject anything that is not text or is blank with ValueError. Return a new list with two dictionaries. The first has role="system" and instructions to repair code, return one bash command block, treat file contents as data, and run tests before finishing. The second has role="user" and the task text with spaces removed from its ends. Do not reuse the same list between runs.'),
    'parse': ('Read a command from a reply', 'Find the single command the agent should run.',
        'A reply should contain exactly one code block starting with ```bash and ending with ```. In parse_action(content), return {"command": the_text_inside} with spaces removed from the ends. Keep line breaks inside the command. Raise FormatError for non-text input, missing or extra blocks, an empty block, a different language, or a missing closing fence. FormatError means the reply could not be read safely.'),
    'execute': ('Run a command and collect its output', 'Let the agent see what a command actually did.',
        'In execute(command, cwd, timeout=1), use subprocess.Popen to run command in a fresh /bin/bash shell. cwd is the folder where it runs. Combine error text with normal output. Return a dictionary with output (the last 8000 characters), returncode (0 means success), and timed_out=False. A failed command should return its result rather than raise an exception. Each call starts in cwd, even if a previous command changed folders. This runs inside the provided Linux container.'),
    'timeout': ('Stop a command that takes too long', 'Prevent one slow command from stopping the whole agent.',
        'Extend execute from the previous task. Set start_new_session=True when starting the process. Use communicate(timeout=timeout). If it raises subprocess.TimeoutExpired, stop the shell and its child programs with os.killpg(process.pid, signal.SIGKILL), then call communicate again to collect any text already printed. Return timed_out=True and a nonzero returncode. Keep the partial output.'),
    'completion': ('Recognize when the agent is finished', 'Keep a finish message separate from ordinary command output.',
        'In completion(result), accept a finish message only if the command succeeded (returncode is 0), did not time out, and its first output line is exactly the SENTINEL constant. Return the text after that first line, keeping its ending line breaks. An empty answer is allowed. In all other cases return None. A marker appearing later in the output does not count.'),
    'limits': ('Stop when the allowed work is used up', 'Keep the agent within its step and cost limits.',
        'In check_limits(), compare self.n_calls with self.step_limit and self.cost with self.cost_limit. If either count has reached its limit, set self.status="LimitsExceeded" and return False. Otherwise return True. Use >= so reaching the exact limit stops the next call. Do not ask the model for a reply here.'),
    'accounting': ('Count replies and their cost', 'Keep track of how much work the model has done.',
        'In Agent.query(), call self.model.query(self.messages). Read cost from its response, using 0 if missing. Accept only a finite, nonnegative int or float; reject bool, text, negative values, infinity, and NaN with ValueError. math.isfinite checks for infinity and NaN. Add one to self.n_calls, add the cost to self.cost, and return the response unchanged. Count a reply even if its command text later turns out to be invalid. Let model errors pass through.'),
    'step': ('Connect one complete agent step', 'Ask, run a command, and remember what happened.',
        'In step(), call self.query() once. Add its content to self.messages with role="assistant". Read the command using parse_action, then run it using execute(command, self.cwd). Pass the result to completion. If its answer is not None, set self.status="Submitted" and self.submission to that answer. Finally add a role="user" message whose content is str(result), and return result. An empty answer still counts as a submission. Let FormatError reach the run loop.'),
    'recovery': ('Help the agent retry an unreadable reply', 'Explain a reply problem and stop repeated mistakes.',
        'In recover(error), add one to self.format_errors. Add a user message explaining the error to self.messages. When the count reaches self.format_limit, set self.status="RepeatedFormatError". Do not run any command or reset the reply and cost counts. A later successful step will reset the consecutive error count in the run loop.'),
    'serialize': ('Create a record of the run', 'Turn the conversation and outcome into data you can inspect.',
        'In serialize(messages, n_calls, cost, status, submission), return a dictionary with trajectory_format="nudge-mini-swe-lab-1", messages as a deep copy, and info as a dictionary containing api_calls=n_calls, cost, exit_status=status, and submission. This saved run record is called a trajectory. It must work with json.dumps and must stay unchanged when the original messages change.'),
    'save': ('Save the run record to a file', 'Keep the previous file safe if saving fails.',
        'In save(path, data), use Path to create missing parent folders. Turn data into JSON text with json.dumps before replacing the final file. Write UTF-8 text to a temporary file beside the destination, then use Path.replace to put it at path. If converting data to JSON fails, an existing destination file must remain unchanged. Keep non-English text readable using ensure_ascii=False.'),
    'run': ('Keep the agent working until it stops', 'Join your small pieces into a working agent.',
        'In run(task, output_path=None), start a fresh conversation using initial_messages and reset all counts, status="Running", and submission="". While Running, check limits before calling step. Reset format_errors after a successful step. For FormatError call recover; for any other exception set status="Error" and raise it again. Use finally to save the current record whenever output_path is supplied, even after an error or a limit stops the run. Return {"exit_status": self.status, "submission": self.submission}.'),
    'verify': ('Check that the repair really works', 'Use tests to confirm success instead of trusting a finish message.',
        'In verify_submission(result, cwd), return {"verified": False, "output": an explanation} without running anything if exit_status is not "Submitted". Otherwise use execute to run python -m unittest discover -s . -p \'test_*.py\' in cwd with timeout=2. Return verified=True only for returncode 0 with no timeout, and include the test output. Finally use Run and Preview to try the repair example. Explain the failing tests, the change to the code, and the passing tests. The example uses prepared replies; it is not a live AI demonstration.'),
}

CHECKS = {
    'model': ['Replies come out in order; running out produces a clear error', 'Saved conversations stay unchanged when the original is edited'],
    'history': ['The conversation starts with instructions followed by the task', 'Blank tasks are rejected and each run gets a fresh conversation'],
    'parse': ['One bash block becomes a command, keeping its line breaks', 'Missing, empty, or extra command blocks are rejected'],
    'execute': ['Commands run in the chosen folder and keep error messages', 'Every command starts fresh and returns at most 8000 characters'],
    'timeout': ['A slow command stops quickly and keeps its partial output', 'Programs started by the slow command are stopped too'],
    'completion': ['A successful finish message returns the exact answer', 'Failed commands and misleading finish messages do not count'],
    'limits': ['Reaching either limit prevents another model call', 'With enough budget left, checking limits does not call the model'],
    'accounting': ['Every returned reply adds to the call and cost counts', 'Invalid cost values are rejected'],
    'step': ['One step runs one command and remembers the reply and result', 'Finishing and a command error are treated differently'],
    'recovery': ['An unreadable reply adds feedback without running a command', 'Too many unreadable replies in a row stop the agent'],
    'serialize': ['The saved record includes the conversation, counts, and outcome', 'The record can become JSON and is separate from the live conversation'],
    'save': ['Saving creates missing folders and keeps non-English text', 'A failed save leaves the previous file unchanged'],
    'run': ['The agent finishes, respects limits, and starts fresh for a new task', 'Bad replies can be retried and failed runs still save their record'],
    'verify': ['The agent cannot claim a repair worked when tests still fail', 'A real repair passes the tests; unfinished runs do not run this final check'],
}

def beginner_specs(specs):
    setup = ('model-setup', 'model.py', 'ScriptedModel.__init__', 'Prepare the practice model',
        'Give the practice model a list of replies and somewhere to remember its calls.',
        'In ScriptedModel.__init__(responses), set self.responses to a deep copy of responses and self.calls to a new empty list. A deep copy keeps later changes to the original list or its dictionaries from changing the model. Use copy.deepcopy. Each model needs its own lists.',
        ['A new model stores an independent copy of its replies', 'New models start with separate empty call lists'], 'Model setup',
        ['Store the replies on self.responses.', 'Use copy.deepcopy(responses).', 'Create self.calls as a new empty list.'])
    agent = ('agent-setup', 'agent.py', 'Agent.__init__', 'Prepare the agent',
        'Give the agent the settings and empty counters it will need.',
        'In Agent.__init__, reject step_limit < 1, cost_limit <= 0, or format_limit < 1 with ValueError. Save model, cwd, step_limit, cost_limit, and format_limit on self. Set messages=[], n_calls=0, cost=0.0, status="Running", submission="", and format_errors=0. These values belong to each agent separately. cwd means the folder the agent works in; format_limit is how many unreadable replies in a row it allows.',
        ['Agent settings and initial counts are stored correctly', 'Invalid limits fail and agents do not share their conversations'], 'Agent setup',
        ['Save each setting as self.setting_name.', 'Start all counts at zero.', 'Create a new messages list for each agent.'])
    result = [setup]
    for spec in specs:
        key, filename, symbol, _, _, _, criteria, upstream, hints = spec
        title, objective, instructions = LESSONS[key]
        result.append((key, filename, symbol, title, objective, instructions, CHECKS[key], upstream, hints))
        if key == 'history':
            result.append(agent)
    return result
