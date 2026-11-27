"""Trusted behavior checks, executed only in Nudge's isolated runtime."""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from model import ScriptedModel
from agent import Agent, initial_messages
from parser import parse_action, FormatError
from environment import execute, completion, SENTINEL
from trajectory import serialize, save
from evaluation import verify_submission


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def raises(kind, operation):
    try:
        operation()
    except kind:
        return
    raise AssertionError(f"Expected {kind.__name__}")


def response(command="printf hello", cost=0.01):
    return {"content": "```bash\n" + command + "\n```", "cost": cost}


def check(key, case, cwd):
    if key == "model-setup":
        replies = [response()]
        model = ScriptedModel(replies)
        if case == 0:
            replies[0]['content'] = 'changed'
            require(model.responses[0]['content'] != 'changed', 'Keep a separate copy of replies')
        else:
            other = ScriptedModel([])
            model.calls.append('one call')
            require(other.calls == [], 'Each model starts with its own empty call list')
    elif key == "agent-setup":
        model = ScriptedModel([])
        agent = Agent(model, cwd, step_limit=3, cost_limit=.5, format_limit=4)
        if case == 0:
            require(agent.model is model and agent.cwd == cwd and agent.step_limit == 3 and agent.cost_limit == .5 and agent.format_limit == 4, 'Remember the supplied settings')
            require(agent.messages == [] and agent.n_calls == 0 and agent.cost == 0 and agent.status == 'Running' and agent.submission == '' and agent.format_errors == 0, 'Start with empty history and zero counts')
        else:
            for kwargs in [{'step_limit': 0}, {'cost_limit': 0}, {'format_limit': 0}]:
                raises(ValueError, lambda: Agent(model, cwd, **kwargs))
            agent.messages.append('one message')
            require(Agent(model, cwd).messages == [], 'Each agent owns a separate conversation')
    elif key == "model":
        if case == 0:
            model=ScriptedModel([response("echo one"),response("echo two")])
            require("one" in model.query([])["content"] and "two" in model.query([])["content"],"Consume in FIFO order")
            raises(RuntimeError,lambda:model.query([]))
        else:
            messages=[{"role":"user","content":"task"}];model=ScriptedModel([response()]);model.query(messages)
            messages[0]["content"]="changed"
            require(model.calls==[[{"role":"user","content":"task"}]],"History must be deep-copied")
    elif key == "history":
        if case == 0:
            history=initial_messages("  fix addition  ")
            require([m["role"] for m in history]==["system","user"] and history[1]["content"]=="fix addition" and bool(history[0]["content"]),"Create ordered system and task messages")
        else:
            for value in [None,42,"","   "]: raises(ValueError,lambda:initial_messages(value))
            one=initial_messages("one");two=initial_messages("two");one[0]["content"]="edited"
            require(two[0]["content"]!="edited","Do not share run state")
    elif key == "parse":
        if case == 0:
            require(parse_action("Inspect first\n```bash\npwd\ncat example.py\n```\n")=={"command":"pwd\ncat example.py"},"Preserve the complete action")
        else:
            for value in [None,"echo hi","```bash\n\n```","```python\npass\n```","```bash\necho one\n```\n```bash\necho two\n```","```bash\necho missing"]:
                raises(FormatError,lambda:parse_action(value))
    elif key == "execute":
        if case == 0:
            result=execute("printf problem >&2; exit 7",cwd)
            require(result["returncode"]==7 and "problem" in result["output"] and result["timed_out"] is False,"Keep stderr and nonzero status")
        else:
            execute("cd /",cwd)
            require(execute("pwd",cwd)["output"].strip()==str(Path(cwd).resolve()),"Shell cwd must not leak between actions")
            result=execute("python -c \"print('x'*10000)\"",cwd)
            require(len(result["output"])==8000,"Bound tool output to 8000 characters")
    elif key == "timeout":
        if case == 0:
            start=time.monotonic();result=execute("python -u -c \"import time; print('partial',flush=True); time.sleep(3)\"",cwd,timeout=.2)
            require(result["timed_out"] and result["returncode"]!=0 and "partial" in result["output"] and time.monotonic()-start<2,"Return partial timeout evidence promptly")
        else:
            execute("python -c \"import time; from pathlib import Path; time.sleep(.6); Path('orphan').write_text('leaked')\" & wait",cwd,timeout=.15)
            time.sleep(.7)
            require(not (Path(cwd)/"orphan").exists(),"A timed-out child process survived")
    elif key == "completion":
        if case == 0:
            require(completion({"output":SENTINEL+"\nanswer\n","returncode":0,"timed_out":False})=="answer\n","Preserve exact submitted text")
            require(completion({"output":SENTINEL+"\n","returncode":0})=="","Empty submission is distinct from no submission")
        else:
            for result in [{"output":SENTINEL+"\nanswer","returncode":1},{"output":"log\n"+SENTINEL,"returncode":0},{"output":SENTINEL,"returncode":0,"timed_out":True},{"output":"","returncode":0}]:
                require(completion(result) is None,"Do not accept misleading completion markers")
    elif key == "limits":
        agent=Agent(ScriptedModel([]),cwd,step_limit=2,cost_limit=.5)
        if case == 0:
            agent.n_calls=2;require(agent.check_limits() is False and agent.status=="LimitsExceeded","Enforce the exact step limit")
            agent.n_calls=0;agent.status="Running";agent.cost=.5
            require(agent.check_limits() is False and agent.status=="LimitsExceeded","Enforce the exact cost limit")
        else:
            require(agent.check_limits() is True and agent.status=="Running" and not agent.model.calls,"Checking limits must not query the model")
    elif key == "accounting":
        if case == 0:
            agent=Agent(ScriptedModel([response(cost=.1),{"content":"bad format","cost":.2}]),cwd)
            agent.query();agent.query()
            require(agent.n_calls==2 and abs(agent.cost-.3)<1e-9,"Malformed content is still billed")
        else:
            for cost in [-1,float('inf'),float('nan'),True,"free"]:
                raises(ValueError,lambda:Agent(ScriptedModel([response(cost=cost)]),cwd).query())
    elif key == "step":
        agent=Agent(ScriptedModel([response()]),cwd);agent.messages=initial_messages("fix")
        if case == 0:
            with patch('agent.execute',return_value={"output":"hello","returncode":0,"timed_out":False}) as tool:
                agent.step();require(tool.call_count==1 and tool.call_args.args==('printf hello',cwd),"Execute exactly once in the repository")
            require([m['role'] for m in agent.messages]==['system','user','assistant','user'] and 'hello' in agent.messages[-1]['content'],"Record a linear trajectory")
        else:
            with patch('agent.execute',return_value={"output":SENTINEL+'\ndone','returncode':0}): agent.step()
            require(agent.status=='Submitted' and agent.submission=='done',"Recognize protocol submission")
            agent=Agent(ScriptedModel([response()]),cwd)
            with patch('agent.execute',return_value={"output":"broken","returncode":3}): agent.step()
            require(agent.status=='Running' and 'broken' in agent.messages[-1]['content'],"A command failure is an observation")
    elif key == "recovery":
        agent=Agent(ScriptedModel([]),cwd,format_limit=2)
        if case == 0:
            with patch('agent.execute',side_effect=AssertionError('Must not execute')):
                agent.recover(FormatError('one bash block'))
            require(agent.format_errors==1 and agent.status=='Running' and agent.messages[-1]['role']=='user' and 'one bash block' in agent.messages[-1]['content'],"Record correction without executing")
        else:
            agent.recover(FormatError('first'));agent.recover(FormatError('second'))
            require(agent.status=='RepeatedFormatError' and agent.n_calls==0 and agent.cost==0,"Bound retries without resetting accounting")
    elif key == "serialize":
        messages=[{"role":"user","content":"fix"}];data=serialize(messages,3,.2,'Submitted','patch')
        if case == 0:
            require(data['info']=={'api_calls':3,'cost':.2,'exit_status':'Submitted','submission':'patch'} and data['trajectory_format']=='nudge-mini-swe-lab-1',"Include schema and outcome evidence")
        else:
            messages[0]['content']='changed'
            require(json.loads(json.dumps(data))['messages'][0]['content']=='fix',"Evidence must be detached and JSON-compatible")
    elif key == "save":
        path=Path(cwd)/'nested/trajectory.json'
        save(path,{'message':'café'})
        if case == 0:
            require(json.loads(path.read_text(encoding='utf-8'))=={'message':'café'},"Save valid UTF-8 JSON in nested directories")
        else:
            raises(TypeError,lambda:save(path,{'bad':object()}))
            require(json.loads(path.read_text())=={'message':'café'},"Failed serialization must not overwrite the last good file")
    elif key == "run":
        finish=response("printf '"+SENTINEL+"\\ndone\\n'")
        if case == 0:
            agent=Agent(ScriptedModel([finish,finish]),cwd)
            require(agent.run('first')['exit_status']=='Submitted',"Run must terminate on submission")
            agent.run('second');require(agent.n_calls==1 and agent.messages[1]['content']=='second',"Reset state per run")
            limited=Agent(ScriptedModel([response(),response()]),cwd,step_limit=1)
            require(limited.run('bounded')['exit_status']=='LimitsExceeded' and limited.n_calls==1,"Check limits before the next query")
        else:
            sequence=[{'content':'bad','cost':.1},response(),{'content':'bad again','cost':.1},finish]
            agent=Agent(ScriptedModel(sequence),cwd,format_limit=2);path=Path(cwd)/'trace.json'
            require(agent.run('recover',path)['exit_status']=='Submitted' and agent.n_calls==4,"A clean step must reset consecutive format errors")
            class Broken:
                def query(self,messages): raise RuntimeError('provider unavailable')
            raises(RuntimeError,lambda:Agent(Broken(),cwd).run('fail',path))
            require(json.loads(path.read_text())['info']['exit_status']=='Error',"Save failure evidence in finally")
    elif key == "verify":
        from demo import BUGGY, TEST
        root=Path(cwd);(root/'calculator.py').write_text(BUGGY);(root/'test_calculator.py').write_text(TEST)
        if case == 0:
            result=verify_submission({'exit_status':'Submitted'},cwd)
            require(result['verified'] is False and 'FAIL' in result['output'],"A model claim must not bypass failing tests")
        else:
            (root/'calculator.py').write_text('def add(a,b):\n    return a+b\n')
            require(verify_submission({'exit_status':'Submitted'},cwd)['verified'] is True,"Verify the real repaired repository")
            with patch('evaluation.execute',side_effect=AssertionError('No submission')):
                require(verify_submission({'exit_status':'LimitsExceeded'},cwd)['verified'] is False,"Do not test non-submissions")


def run(task_id, add_result, criteria):
    for index, criterion in enumerate(criteria):
        try:
            with tempfile.TemporaryDirectory() as cwd:
                check(task_id.removeprefix('mini-swe-'), index, cwd)
            add_result(criterion, True, 'Observed the required behavior.')
        except Exception as error:
            add_result(criterion, False, f'{type(error).__name__}: {error}')
