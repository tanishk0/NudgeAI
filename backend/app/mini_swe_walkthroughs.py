"""Beginner-facing explanations and examples, separate from verifier contracts."""

PURPOSE = {
    'model-setup': (
        'Our finished agent will receive a task such as “fix the calculator” and ask a model what to do next. For this exercise, the model has a list of prepared replies. Before it can give out replies, it needs somewhere to keep them and somewhere to record the questions it receives.',
        'Write the setup method that creates those two lists for each practice model.',
        'responses: a list of reply dictionaries, such as [{"content": "Read calculator.py"}].',
        'The method stores a separate copy in self.responses and an empty list in self.calls. It does not return a reply yet.'),
    'model': (
        'Imagine the agent has been asked to fix a calculator. It needs to ask “what should I do next?” and receive a reply such as “read calculator.py.” Later, the agent will call query(messages) to get that reply. Until this function works, the agent cannot receive its next instruction. For this exercise we supply prepared replies, so you can build and test the agent without connecting it to a paid model service.',
        'Write a function that remembers the conversation it was given and hands back the next prepared reply. Each call uses up one reply, so the following call gets the next one.',
        'messages: the current conversation, stored as a list of dictionaries. self.responses already holds the prepared replies; self.calls is the list where you record conversations.',
        'Return one reply dictionary unchanged, such as {"content": "Read calculator.py"}. Also add a separate copy of messages as one item in self.calls. Raise RuntimeError if there are no replies left.'),
    'history': (
        'When you ask someone to fix a bug, you first explain the task and the rules. The agent needs the same starting information. Later, run(task) will call this function to create the conversation that is sent to the model.',
        'Write a function that turns the task text into two starting messages: ground rules first, the person’s request second.',
        'task: the person’s request as text, such as "Fix the calculator".',
        'Return a new list of two message dictionaries. Invalid or blank task text raises ValueError.'),
    'agent-setup': (
        'The agent will connect all the parts you are building: ask for a reply, run its command, and remember the result. Before it starts, it needs a working folder, sensible limits, and empty counters. Later methods will read the settings you save here.',
        'Write the setup method that saves the supplied settings and prepares a fresh agent with no work recorded yet.',
        'A model object, a working folder named cwd, and the allowed step, cost, and repeated-error limits.',
        'Save the settings on self, create the empty conversation and counters, and reject invalid limits with ValueError.'),
    'parse': (
        'A model reply can contain an explanation as well as a terminal command. The next part of the agent needs the command by itself so it can run it. It also needs a clear error when the reply contains no usable command or more than one possible command.',
        'Write a function that extracts exactly one command from a reply’s bash code block.',
        'content: the model’s reply as text. For example, a bash code block containing pwd.',
        'Return {"command": "pwd"} for that example. Raise FormatError when the reply cannot be read unambiguously.'),
    'execute': (
        'The agent has a command such as “show the files,” but a command written in text does nothing on its own. Later, step() will use this function to actually run it and send the printed result back to the model, so the model can decide what to do next.',
        'Write a function that runs one command in the chosen folder and reports what happened.',
        'command: terminal command text. cwd: the folder to run it in. timeout: the allowed time, used in the next task.',
        'Return a dictionary containing output, returncode, and timed_out. A zero returncode means success.'),
    'timeout': (
        'A command might wait forever. Without a timer, one slow command can prevent the agent from ever continuing. You will extend the function from the previous task so it returns control and any useful text when time runs out.',
        'Add a time limit to execute(), stopping the command and the programs it started when the limit is reached.',
        'The same command and folder as before, plus timeout as a number of seconds.',
        'Return the same result dictionary. When time runs out, timed_out is True, returncode indicates failure, and output keeps any text printed so far.'),
    'completion': (
        'The agent needs to know when to stop asking for more work. Ordinary output such as a list of files should keep the loop going; a special finish message should stop it. Later, step() will use your answer to decide whether the run is finished.',
        'Write a function that recognizes a valid finish message and extracts the final answer.',
        'result: the dictionary returned by execute(), containing printed output and whether the command succeeded.',
        'Return the final-answer text when a successful command starts with the special marker. Otherwise return None.'),
    'limits': (
        'An agent could keep asking for replies without ever fixing the bug. Each reply also uses a share of the budget. Before each step, run() will ask this function whether there is enough allowance left to continue.',
        'Write a check that stops further work once either the reply limit or the cost limit is reached.',
        'Read the current counts and their limits from self. This method takes no extra argument.',
        'Return True if more work is allowed. Otherwise set status to LimitsExceeded and return False.'),
    'accounting': (
        'The limit checker needs accurate totals. Every reply that comes back from the model must be counted, even if its text is unusable. Later, step() will call this method to get a reply and keep those totals up to date.',
        'Write the agent’s reply-requesting method: get one response, check its cost, and update the totals.',
        'Read self.model and self.messages. The model returns a response dictionary that can include cost.',
        'Return that response unchanged, after updating self.n_calls and self.cost. Reject invalid cost values.'),
    'step': (
        'You have built separate helpers for asking, reading commands, running commands, and recognizing a finish message. The agent now needs them connected in the right order. The run loop will repeat this one step until the agent finishes or reaches a limit.',
        'Write one complete turn of the agent, using your existing helpers and recording both the reply and the command result.',
        'Use the model, conversation, and working folder saved on self.',
        'Return the command result. Update the conversation, and record Submitted plus the final answer if a valid finish message was found.'),
    'recovery': (
        'A model can return an explanation without the required command block. Giving it a correction lets it try again. Counting repeated mistakes keeps that retry process from continuing forever. run() will call this helper after catching FormatError.',
        'Write a helper that records the format problem, counts it, and stops the run after too many mistakes in a row.',
        'error: the FormatError describing what was wrong with the reply.',
        'Update the conversation and format_errors count on self. Set RepeatedFormatError when the limit is reached; no return value is required.'),
    'serialize': (
        'After a run, someone should be able to inspect what the agent asked, what it saw, and how it stopped. The file-saving function needs these separate pieces collected into one plain data structure first.',
        'Write a function that packages the conversation, counters, and outcome into a separate record.',
        'messages, n_calls, cost, status, and submission: the conversation and the current run’s results.',
        'Return one dictionary containing trajectory_format, messages, and info. Later edits to the original conversation must leave this record unchanged.'),
    'save': (
        'A record kept only in memory disappears when the program ends. Saving it lets you reopen and inspect the run later. Preparing a new file before replacing the old one protects the previous record if something goes wrong.',
        'Write a function that saves a run record as JSON text and safely replaces an older saved record.',
        'path: the destination file name. data: the record to save.',
        'Create the file and any missing folders. A failed conversion to JSON must leave an existing saved file intact. No return value is required.'),
    'run': (
        'The agent needs someone to coordinate the whole job: start a conversation, repeat steps, enforce limits, handle errors, and save the result. This function is that coordinator. The supplied repair example will call it to ask your completed agent to fix a bug.',
        'Write the main loop using the helpers you have already built. Keep going only while status is Running.',
        'task: the repair request. output_path: an optional place to save the run record.',
        'Return the final exit_status and submission. Save the record when a path was supplied, including if the run stops because of an error or a limit.'),
    'verify': (
        'The agent saying “finished” does not prove the bug was fixed. The presentation needs evidence that the repaired code works. After the agent stops, this separate check runs the project’s tests and reports their actual result.',
        'Write the final check that runs tests only after the agent has submitted its work.',
        'result: the outcome returned by Agent.run(). cwd: the folder containing the repaired code and tests.',
        'Return verified as True or False together with output explaining the result. Only successful tests within the time limit count as verified.'),
}

EXAMPLES = {
    'model-setup': (
        'Think of the practice model as a queue of prepared replies. This task only prepares the queue; the next task will take replies out of it. In a Python class, `self` means this particular object. `self.responses` is the list this model owns. `self.calls` will remember each conversation sent to it. A deep copy makes a separate list and separate dictionaries inside it.',
        'model = ScriptedModel([{"content": "Hello"}])\nprint(model.responses)\nprint(model.calls)',
        'The first print shows [{"content": "Hello"}]. The second shows []. If you create a second model, it must have its own empty calls list.'),
    'model': (
        'Imagine a stack of numbered reply cards. Each call takes the next card and remembers what was asked. `messages` is the conversation being passed in. Save its copy as ONE item in the calls list; do not add each individual message separately. Use `.append(...)` to add one item and `.pop(0)` to take the first reply out of a list.',
        'model = ScriptedModel([\n    {"content": "Read calculator.py"},\n    {"content": "Run its tests"},\n])\nmessages = [{"role": "user", "content": "Fix the calculator"}]\nprint(model.query(messages))\nprint(model.query(messages))',
        'The first call returns {"content": "Read calculator.py"}; the second returns {"content": "Run its tests"}. These short reply texts are practice data for this function; you will read actual terminal commands in a later task. self.calls now holds two separate copies of the conversation that was sent in. A third call raises RuntimeError because no reply is left. An exception such as RuntimeError clearly reports that an operation cannot continue.'),
    'history': (
        'The agent needs two messages before it starts: the ground rules, then the person’s request. Each message is a Python dictionary with role and content. The role says who the message comes from. A system message contains ground rules; a user message contains the task. `.strip()` removes spaces at the ends of text.',
        'messages = initial_messages("  Fix the add function  ")\nprint(messages[0]["role"])\nprint(messages[1])',
        'You see system, then {"role": "user", "content": "Fix the add function"}. Calling this function with blank text must raise ValueError, which means the supplied value is unsuitable.'),
    'agent-setup': (
        'This task sets up the object that coordinates the work. `cwd` is its working folder. `step_limit` is the maximum number of model replies. `cost_limit` is the allowed simulated cost. `format_limit` is the allowed number of unreadable replies in a row. Save each argument on self so later methods can use it. The fields messages, n_calls, cost, and format_errors start empty or at zero because no work has happened yet.',
        'agent = Agent(model, "/workspace", step_limit=3)\nprint(agent.n_calls)\nprint(agent.status)\nprint(agent.messages)',
        'You see 0, Running, and []. Passing step_limit=0 must raise ValueError. This task does not run commands or ask for a model reply.'),
    'parse': (
        'The model writes a reply, but the computer needs just the command inside it. Bash is the terminal program used to run that command. Three backticks mark the start and end of a code block. Accept one block labelled bash. If the reply is unclear, raise the provided FormatError instead of guessing which command to run.',
        r'reply = "```bash\npwd\n```"' + '\nprint(parse_action(reply))',
        'The result is {"command": "pwd"}. pwd prints the current folder. A reply with no code block, an empty block, or two blocks must raise FormatError.'),
    'execute': (
        'Now run a command and collect the text it prints. A process is a running program. `subprocess.Popen` starts it; `.communicate()` waits for it and collects its output. Use shell=True, executable="/bin/bash", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, and text=True. `cwd` chooses the folder. `returncode` is the program’s result number: zero means success. Starting a fresh shell each time keeps commands independent.',
        'result = execute("printf hello", "/workspace")\nprint(result)',
        'The result contains output="hello", returncode=0, and timed_out=False. A command that exits with an error must still return its output and result number. This exercise runs inside the provided Linux container, not your Windows terminal.'),
    'timeout': (
        'Keep your previous command-running code and add a timer. A timeout means the command took longer than allowed. The command might start other programs, so stop the whole group, not only the first program. start_new_session=True puts them in one group; killpg stops that group. Keep text printed before the timer expired so the person can understand what happened.',
        'result = execute("printf started; sleep 3", "/workspace", timeout=0.2)\nprint(result["timed_out"])\nprint(result["output"])',
        'You see True and output containing started. The call returns quickly rather than waiting all three seconds.'),
    'completion': (
        'Most command output is just information. A special first line means “I am finished.” SENTINEL is the provided constant containing that exact marker. Only accept it after a successful command. None means no finish message was found; an empty string means the agent finished with an empty answer. Those are different cases.',
        r'result = {"output": SENTINEL + "\nFixed it!\n", "returncode": 0, "timed_out": False}' + '\nprint(repr(completion(result)))',
        'The answer is \'Fixed it!\\n\'. If returncode is 1, the answer is None. Use splitlines(keepends=True) so you can remove the first line without losing the answer’s line breaks.'),
    'limits': (
        'Before another reply is requested, check whether the agent has used its allowance. n_calls counts replies already received; cost is their total simulated cost. Reaching either limit is enough to stop. Use >=, because using exactly the allowance means there is none left for another call.',
        'agent.n_calls = agent.step_limit\nprint(agent.check_limits())\nprint(agent.status)',
        'You see False and LimitsExceeded. If both counts are below their limits, return True and keep the status unchanged. This check itself must not ask the model for a reply.'),
    'accounting': (
        'This method asks for one reply and updates the totals. A response is a dictionary; its cost value is a number. `.get("cost", 0)` supplies zero when that key is missing. Python treats True as a kind of integer, so reject booleans explicitly before checking for int or float. math.isfinite rejects special values such as infinity and NaN, which would make the totals unreliable.',
        '# Suppose the next reply has cost 0.25 and the counters start at zero.\nreply = agent.query()\nprint(agent.n_calls)\nprint(agent.cost)',
        'You see 1 and 0.25. Even an unreadable reply counts, because it was still received. A cost such as -1 or "free" must raise ValueError.'),
    'step': (
        'A step is one trip around the loop: get a reply, read its command, run the command, and remember the result. Use the helper functions you already built instead of implementing them again. Add the model’s words as an assistant message. Add the command result as a user message so the model can read it on the next turn.',
        '# Suppose the next reply asks the agent to run: printf hello\nresult = agent.step()\nprint(result["output"])\nprint(agent.messages[-1]["role"])',
        'You see hello and user. If completion(result) returns anything except None, also record that answer and set status to Submitted. Submitted means the agent says it is finished; a later task will check whether the repair really works.'),
    'recovery': (
        'When a reply cannot be read, record a clear correction so the next reply can improve. Keep a separate count of these mistakes in a row. Do not reset how many replies were used or what they cost. This helper only records feedback; it does not run another command or retry by itself.',
        'agent.recover(FormatError("Please send one bash block"))\nprint(agent.format_errors)\nprint(agent.messages[-1]["role"])',
        'Starting from zero, the count becomes 1 and the new message has role user. Reaching format_limit changes status to RepeatedFormatError.'),
    'serialize': (
        'Create a plain dictionary describing the run, ready to save. This is called serializing. JSON is a text format for storing lists, dictionaries, numbers, and strings. The saved record must contain its own copy of the conversation so later edits do not rewrite history. trajectory_format is just a label saying which version of the saved-file layout you use.',
        'record = serialize([], 2, 0.25, "Submitted", "Fixed")\nprint(record["info"]["api_calls"])\nprint(record["info"]["exit_status"])',
        'You see 2 and Submitted. json.dumps(record) should succeed, and the messages list in record must be separate from the input list.'),
    'save': (
        'Save a record without risking the previous good file. First prepare all the JSON text. Write it to a temporary file beside the destination. Only after that succeeds, replace the destination. Path is Python’s helper for file paths; parent is the containing folder. UTF-8 is the text encoding that preserves characters from different languages.',
        'save("runs/example.json", {"message": "Hello"})\n# Then open runs/example.json and read its contents.',
        'The runs folder is created if needed and the file contains a JSON object with message="Hello". If data cannot be converted to JSON, a previously saved file stays unchanged.'),
    'run': (
        'This is the final coordinator, not another place to write the individual helpers. First reset the state, then repeat one step while the status is Running. Stop before a limit is exceeded. A try/except block decides how to handle an error; finally runs cleanup whether the step succeeds or fails. Use that finally block to save the record even when a run stops unexpectedly.',
        'result = agent.run("Fix the add function", output_path="runs/latest.json")\nprint(result["exit_status"])',
        'The result reports Submitted, LimitsExceeded, or RepeatedFormatError, depending on what happened. Unexpected errors are raised again after status becomes Error and the record is saved. Starting another run resets the previous counts and conversation.'),
    'verify': (
        'A finish message is a claim, not proof. Run the repaired project’s tests to check it. unittest is Python’s built-in test runner; discover finds test files. The supplied command looks for files named test_*.py in the working folder. verified is True only if those tests finish successfully within the time limit.',
        'result = verify_submission({"exit_status": "Submitted"}, "/workspace")\nprint(result["verified"])\nprint(result["output"])',
        'You see True only when the tests pass. Failing tests give False and their output explains the problem. If the agent did not submit, return False without running tests.'),
}


def lesson_brief(key, filename, symbol, number, total, instructions):
    explanation, example, expected = EXAMPLES[key]
    why, goal, receives, produces = PURPOSE[key]
    # Keep the complete behavior contract, but turn top-level bullets into steps.
    body = instructions.split('\n\n', 1)[-1]
    if body.startswith('**What to'):
        body = body.split('\n', 1)[-1]
    lines = []
    count = 0
    for line in body.splitlines():
        if line.startswith('- '):
            count += 1
            line = f'{count}. {line[2:]}'
        lines.append(line)
    steps = '\n'.join(lines)
    return (
        f'**Task {number} of {total}**\n\n'
        f'### Why this part exists\n{why}\n\n'
        f'### Your job in this task\n{goal}\n\n'
        f'**What it receives:** {receives}\n\n**What it must produce:** {produces}\n\n'
        f'### Start here\nOpen `{filename}` and find `{symbol}`. Write the behavior described above inside this function. '
        'The line `raise NotImplementedError` marks a missing implementation; replace it as you build the steps below. '
        'Other unfinished functions can stay as they are.\n\n'
        f'### What you are making\n{explanation}\n\n'
        f'### Build it in this order\n{steps}\n\n'
        f'### Example to aim for\n```python\n{example}\n```\n\n**Expected result:** {expected}\n\n'
        '### Check your work\nSave your changes and click **Check task**. Read the result for each check. '
        'When every check passes, the next task unlocks. You do not need the whole app working yet. '
        'If a check fails, ask the mentor about that specific result.'
    )
