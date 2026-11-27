"""One focused pair of behavior checks per curriculum bullet."""
import importlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def raises(kind, operation):
    try:
        operation()
    except kind:
        return
    raise AssertionError(f"Expected {kind.__name__}")


def result(output="done", code=0, timed_out=False):
    return dict(output=output, returncode=code, timed_out=timed_out)


def call(command="pwd", ident="c1"):
    return dict(id=ident, type="function", function=dict(name="bash", arguments=json.dumps(dict(command=command))))


class ModelDouble:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def query(self, messages, tools=None):
        self.calls.append((json.loads(json.dumps(messages)), tools))
        return self.replies.pop(0)


MODULES = {'model': 'minisweagent.models.litellm_model', 'agent': 'minisweagent.agents.default', 'conversation': 'minisweagent.agents.default', 'conversation-loop': 'minisweagent.agents.default', 'prompts': 'minisweagent.agents.default', 'prompt-template': 'minisweagent.agents.default', 'exploration': 'minisweagent.agents.default', 'autonomous-loop': 'minisweagent.agents.default', 'completion': 'minisweagent.agents.default', 'repair-test': 'minisweagent.agents.default', 'budgets': 'minisweagent.agents.default', 'command-execution': 'minisweagent.environments.local', 'command-output': 'minisweagent.environments.local', 'command-timeouts': 'minisweagent.environments.local', 'filesystem': 'minisweagent.environments.local', 'environment-secrets': 'minisweagent.environments.local', 'network': 'minisweagent.environments.local', 'tool-schema': 'minisweagent.models.utils.actions_toolcall', 'tool-binding': 'minisweagent.models.utils.actions_toolcall', 'tool-arguments': 'minisweagent.models.utils.actions_toolcall', 'tool-feedback': 'minisweagent.models.utils.actions_toolcall', 'malformed-tools': 'minisweagent.models.utils.actions_toolcall', 'docker-environment': 'minisweagent.environments.docker', 'container-start': 'minisweagent.environments.docker', 'provision': 'minisweagent.environments.docker', 'container-execution': 'minisweagent.environments.docker', 'lifecycle': 'minisweagent.environments.docker', 'resource-isolation': 'minisweagent.environments.docker', 'api-retries': 'minisweagent.models.utils.retry', 'backoff': 'minisweagent.models.utils.retry', 'exceptions': 'minisweagent.exceptions', 'token-usage': 'minisweagent.utils.serialize', 'output-truncation': 'minisweagent.utils.serialize', 'compaction': 'minisweagent.utils.serialize', 'working-memory': 'minisweagent.utils.serialize', 'trajectory-save': 'minisweagent.utils.serialize', 'session-restore': 'minisweagent.utils.serialize', 'approval': 'minisweagent.agents.utils.prompt_user', 'git-diff': 'minisweagent.run.utilities.inspector'}


def check(key, case, directory):
    m = importlib.import_module(MODULES[key])
    if key == 'initialize':
        root = Path(directory) / 'agent'
        builder = Mock()
        if case:
            root.mkdir(); (root/'requirements.txt').write_text('existing-package\n')
        returned = m.initialize_project(root, builder=builder)
        require(returned == str(root.resolve()), 'Return the absolute project root')
        builder.create.assert_called_once_with(root/'.venv')
        require('.venv/' in (root/'.gitignore').read_text() and '.env' in (root/'.gitignore').read_text(), 'Ignore environments and credentials')
        require((root/'requirements.txt').read_text() == 'existing-package\n' if case else 'litellm' in (root/'requirements.txt').read_text() and 'tenacity' in (root/'requirements.txt').read_text(), 'Preserve existing dependency files')
    elif key == 'model':
        if case:
            for invalid in ['', ' ', 1, None]:
                raises(ValueError, lambda: m.LitellmModel(invalid, complete=Mock()))
        else:
            reply = dict(role='assistant', content='answer')
            provider = Mock(return_value={'choices':[{'message':reply}]})
            model = m.LitellmModel('test/model', complete=provider)
            messages = [dict(role='user', content='hello')]; tools = [{'type':'function'}]
            answer = model.query(messages, tools=tools)
            require(answer == reply and answer is not reply, 'Extract a detached assistant message')
            messages[0]['content']='changed'; tools[0]['type']='changed'
            kwargs = provider.call_args.kwargs
            require(kwargs['model']=='test/model' and kwargs['messages'][0]['content']=='hello' and kwargs['tools'][0]['type']=='function' and kwargs['tool_choice']=='auto', 'Use detached provider arguments')
            boxed = Mock(return_value=SimpleNamespace(model_dump=lambda: {'choices':[{'message':reply}]}))
            require(m.LitellmModel('test/model', complete=boxed).query([])==reply, 'Handle provider model_dump objects')
    elif key == 'agent':
        model = Mock(); agent = m.DefaultAgent(model, system='rules')
        require(agent.model is model and agent.messages == [dict(role='system', content='rules')], 'Store model and system-first history')
        if case:
            other = m.DefaultAgent(model, system='rules'); agent.messages[0]['content']='changed'
            require(other.messages[0]['content']=='rules', 'Agent instances own independent state')
    elif key == 'conversation':
        model = ModelDouble([dict(role='assistant', content='one'), dict(role='assistant', content=None)])
        agent = m.DefaultAgent(model)
        if case:
            for invalid in ['', '  ', 4, None]: raises(ValueError, lambda: agent.chat(invalid))
            require(not model.calls, 'Reject input before querying')
        else:
            require(agent.chat('  hello  ')=='one' and agent.chat('again')=='', 'Return content and handle null')
            require(agent.messages[1]['content']=='hello' and [x['role'] for x in agent.messages]==['system','user','assistant','user','assistant'] and len(model.calls[1][0])==4, 'Persist ordered conversation between turns')
    elif key == 'conversation-loop':
        agent = m.DefaultAgent(Mock()); agent.chat = Mock(side_effect=['one','two'])
        require(agent.run(iter([] if case else ['a','b'])) == ([] if case else ['one','two']), 'Process the input iterable in order')
        require(agent.chat.call_count == (0 if case else 2), 'One chat per input, none for an empty input')
    elif key == 'tool-schema':
        schema = m.bash_schema(); function = schema['function']; params = function['parameters']
        require(schema['type']=='function' and function['name']=='bash' and bool(function['description']), 'Describe the Bash function')
        require(params['type']=='object' and params['required']==['command'] and params['additionalProperties'] is False and params['properties']=={'command':{'type':'string'}}, 'Require exactly one command string')
        if case:
            function['name']='changed'; require(m.bash_schema()['function']['name']=='bash', 'Return independent schemas')
    elif key == 'tool-binding':
        reply = dict(role='assistant', content='answer') if case else dict(role='assistant', tool_calls=[call()])
        model = ModelDouble([reply]); history = [dict(role='user', content='task')]
        require(m.request_action(model, history) is reply, 'Return the response unchanged')
        require(len(model.calls)==1 and model.calls[0][0]==history and model.calls[0][1]==[m.bash_schema()], 'Bind the Bash schema to one query')
    elif key == 'tool-arguments':
        if not case:
            require(m.parse_tool(call('pwd\nprintf hi'))=='pwd\nprintf hi', 'Preserve complete command text')
        else:
            for args in ['{', '[]', 'null', '{"command":4}', '{"command":" "}', '{"command":"pwd","extra":1}']:
                item=call(); item['function']['arguments']=args
                raises(ValueError, lambda: m.parse_tool(item))
            for item in [{}, dict(call(), id=''), dict(call(), type='unknown')]: raises(ValueError, lambda: m.parse_tool(item))
            item=call(); item['function']['name']='unknown'; raises(ValueError, lambda: m.parse_tool(item))
    elif key == 'command-execution':
        if not case:
            observed = m.execute('printf trouble >&2; exit 7', directory)
            require(observed==result('trouble',7), 'Capture stderr and nonzero exit status')
            m.execute('cd /', directory)
            require(m.execute('pwd', directory)['output'].strip()==directory, 'Each action starts in the supplied working directory')
        else:
            observed = m.execute('printf started; sleep 4', directory, timeout=.1)
            require(observed['timed_out'] and observed['returncode']!=0 and 'started' in observed['output'], 'Stop slow process groups and retain partial output')
    elif key == 'command-output':
        if not case:
            original=result('x'*9000,7,True); observed=m.normalize_result(original)
            require(observed==result('x'*8000,7,True) and observed is not original, 'Bound output without losing failure/timeout status')
        else:
            for bad in [dict(output=None,returncode=0,timed_out=False), dict(output='',returncode=True,timed_out=False),dict(output='',returncode=0,timed_out=0),{}]:
                raises(ValueError, lambda: m.normalize_result(bad))
    elif key == 'tool-feedback':
        history=[dict(role='user',content='task')]; runner=Mock(return_value=result('failure',7))
        batch=[call(),call(ident='c2')] if not case else [call(),{'id':'bad'}]
        model=ModelDouble([dict(role='assistant',tool_calls=batch)])
        if case:
            before=json.dumps(history)
            raises(ValueError,lambda:m.tool_turn(model,history,directory,runner))
            require(not runner.called and json.dumps(history)==before,'Validate the entire batch before side effects')
            model=ModelDouble([dict(role='assistant',tool_calls=[call(),call()])])
            raises(ValueError,lambda:m.tool_turn(model,history,directory,runner))
        else:
            m.tool_turn(model,history,directory,runner)
            require(runner.call_count==2 and [x['tool_call_id'] for x in history[2:]]==['c1','c2'], 'Execute and match all requested call ids')
            require(json.loads(history[-1]['content'])==result('failure',7), 'Feed diagnostic output back as JSON')
    elif key == 'prompts':
        text=m.system_prompt(); require(isinstance(text,str),'Return text rules')
        lowered=text.lower()
        require(all(word in lowered for word in (['inspect','reproduce','test'] if not case else ['untrusted','data','final'])),'Explain verification and the repository-data trust boundary')
    elif key == 'prompt-template':
        if case:
            for invalid in ['',None,3,' ']: raises(ValueError,lambda:m.task_messages(invalid,directory))
        else:
            messages=m.task_messages('  fix addition  ',directory)
            require([x['role'] for x in messages]==['system','user'] and messages[0]['content']==m.system_prompt() and directory in messages[1]['content'] and 'fix addition' in messages[1]['content'],'Fill fresh system/task messages')
            messages[0]['content']='changed'; require(m.task_messages('task',directory)[0]['content']!='changed','Do not share prompt state')
    elif key == 'exploration':
        observed=result('file.py',7 if case else 0); runner=Mock(return_value=observed)
        require(m.explore_repository(directory,runner) is observed,'Preserve listing and failure evidence')
        runner.assert_called_once_with('find . -maxdepth 2 -type f | sort',directory,timeout=2)
    elif key == 'autonomous-loop':
        history=[]; replies=[dict(role='assistant',tool_calls=[call()])]*3 if case else [dict(role='assistant',content='done')]
        with patch.object(m,'tool_turn',side_effect=replies) as turn:
            observed=list(m.agent_steps(Mock(),history,directory,Mock(),max_steps=3))
            require(observed==replies and turn.call_count==len(replies),'Bound turns and stop on final answers')
        raises(ValueError,lambda:list(m.agent_steps(Mock(),[],directory,Mock(),max_steps=0)))
    elif key == 'completion':
        if case:
            require(m.submission({'tool_calls':[call()],'content':'working'}) is None,'Tool requests continue the loop')
            for invalid in ['',None,' ']: raises(ValueError,lambda:m.submission({'content':invalid}))
        else:
            require(m.submission({'content':'  Final answer\n'})=='  Final answer\n','Preserve exact final answer')
    elif key == 'repair-test':
        from minisweagent.environments.local import execute
        repository=Path(directory)/'repo'; shutil.copytree(Path('tests/test_data/buggy_repository'),repository)
        require(execute("python -m unittest discover -s . -p 'test_*.py'",str(repository))['returncode']!=0,'Fixture begins broken')
        repair="python -c \"from pathlib import Path; p=Path('calculator.py'); p.write_text(p.read_text().replace('a - b','a + b'))\""
        replies=[dict(role='assistant',content='claimed fixed')] if case else [dict(role='assistant',tool_calls=[call(repair)]),dict(role='assistant',content='repaired')]
        observed=m.run_agent(ModelDouble(replies),'Fix add',str(repository),execute)
        require(observed['status']=='Submitted' and observed['verified'] is (not case),'Independent tests decide verification')
        if case:
            model=ModelDouble([dict(role='assistant',tool_calls=[call()])])
            require(m.run_agent(model,'task',str(repository),execute,max_steps=1)['status']=='LimitsExceeded','Bound a tool-only run')
    elif key == 'docker-environment':
        cli=Mock(); environment=m.DockerEnvironment(cli=cli)
        require(environment.cli is cli and environment.image=='nudge-runtime:local' and not environment.started and environment.name.startswith('mini-swe-') and not cli.called,'Configure without starting Docker')
        if case: require(environment.name!=m.DockerEnvironment(cli=cli).name,'Give environments unique names')
    elif key == 'container-start':
        cli=Mock(side_effect=RuntimeError('start failed')) if case else Mock(return_value=SimpleNamespace(stdout='id',stderr='',returncode=0))
        environment=m.DockerEnvironment(cli=cli); environment.close=Mock()
        with patch.object(m,'sandbox_options',return_value=['--network','none']):
            if case:
                raises(RuntimeError,lambda:environment.start(directory)); environment.close.assert_called_once()
            else:
                require(environment.start(directory) is environment and environment.started,'Start and return the environment')
                args=cli.call_args.args[0]; kwargs=cli.call_args.kwargs
                require(args[:3]==['docker','run','-d'] and args[args.index('--name')+1]==environment.name and any('target=/input,readonly' in arg for arg in args) and kwargs['check'] and kwargs['timeout']==15,'Use a named detached container and read-only source')
    elif key == 'provision':
        cli=Mock(side_effect=RuntimeError('copy failed')) if case else Mock()
        environment=m.DockerEnvironment(cli=cli); environment.close=Mock()
        raises(RuntimeError,environment.provision); environment.started=True
        if case:
            raises(RuntimeError,environment.provision); environment.close.assert_called_once()
        else:
            environment.provision(); cli.assert_called_once_with(['docker','exec',environment.name,'sh','-c','cp -R /input/. /work/'],check=True,capture_output=True,text=True,timeout=10)
    elif key == 'container-execution':
        cli=Mock(side_effect=subprocess.TimeoutExpired('exec',.1,output=b'partial')) if case else Mock(return_value=SimpleNamespace(stdout='x'*9000,stderr='problem',returncode=7))
        environment=m.DockerEnvironment(cli=cli); environment.close=Mock()
        raises(RuntimeError,lambda:environment.execute('pwd')); environment.started=True
        observed=environment.execute('pwd',timeout=.1)
        if case:
            environment.close.assert_called_once(); require(observed['timed_out'] and observed['returncode']!=0 and 'partial' in observed['output'],'Timeout stops the environment and preserves output')
        else:
            require(observed['returncode']==7 and observed['output'].endswith('problem') and len(observed['output'])==8000,'Bound container output and retain error status')
            require(cli.call_args.args[0]==['docker','exec',environment.name,'/bin/bash','-lc','pwd'],'Execute in the container')
    elif key == 'lifecycle':
        cli=Mock(); environment=m.DockerEnvironment(cli=cli); environment.started=True
        environment.close()
        if case: environment.close()
        require(not environment.started and cli.call_count==(2 if case else 1),'Clean up running or already stopped environments')
        require(cli.call_args.args[0]==['docker','rm','-f',environment.name] and cli.call_args.kwargs.get('timeout')==10 and not cli.call_args.kwargs.get('check',False),'Remove the container with bounded cleanup')
    elif key == 'resource-isolation':
        args=m.sandbox_options()
        for flag,value in [('--network','none'),('--cap-drop','ALL'),('--security-opt','no-new-privileges'),('--user','1000:1000'),('--memory','256m'),('--cpus','1'),('--pids-limit','64')]: require(args[args.index(flag)+1]==value,'Enforce '+flag)
        require('--read-only' in args and args.count('--tmpfs')==2 and '/work:rw,uid=1000,gid=1000,size=64m' in args and '/tmp:rw,size=32m' in args and '--privileged' not in args,'Bound writable storage and privileges')
        if case:
            args.append('--privileged'); require('--privileged' not in m.sandbox_options(),'Return independent options')
    elif key == 'api-retries':
        calls=[]; waits=[]
        def request():
            calls.append(1)
            if case: raise ValueError('permanent')
            if len(calls)<3: raise m.TransientAPIError('temporary')
            return 'ready'
        if case:
            raises(ValueError,lambda:m.retry_api(request,sleep=waits.append)); require(len(calls)==1 and not waits,'Do not retry permanent errors')
            request=Mock(side_effect=m.TransientAPIError('outage')); raises(m.TransientAPIError,lambda:m.retry_api(request,attempts=2,sleep=lambda t:None)); require(request.call_count==2,'Bound attempts and reraise last error')
        else: require(m.retry_api(request,sleep=waits.append)=='ready' and waits==[1,2] and len(calls)==3,'Retry transient failures with exponential waits')
    elif key == 'backoff':
        if case:
            for invalid in [0,-1,True,1.5,'1']: raises(ValueError,lambda:m.backoff(invalid))
            require(m.backoff(1000000)==8,'Cap large attempts without unbounded exponentiation')
        else: require([m.backoff(i) for i in range(1,6)]==[1,2,4,8,8],'Calculate capped exponential delays')
    elif key == 'exceptions':
        for kind,expected in [(m.TransientAPIError,'retry'),(m.LimitsExceeded,'stop'),(m.MalformedToolCall,'correct')]: require(m.classify_error(kind('reason'))==expected,'Classify '+kind.__name__)
        if case: require(issubclass(m.MalformedToolCall,ValueError) and m.classify_error(RuntimeError('unexpected'))=='raise','Keep unexpected failures visible')
    elif key == 'malformed-tools':
        runner=Mock(return_value=result('partial',-1,True))
        if case:
            raises(m.MalformedToolCall,lambda:m.safe_tool({},directory,runner)); require(not runner.called,'Malformed calls never execute')
        else:
            require(m.safe_tool(call(),directory,runner)==result('partial',-1,True),'Preserve command evidence'); runner.assert_called_once_with('pwd',directory,timeout=2)
    elif key == 'command-timeouts':
        if case:
            runner=Mock()
            for invalid in [0,-1,True,float('nan'),float('inf'),'2']: raises(ValueError,lambda:m.timed_command('pwd',directory,runner,invalid))
            require(not runner.called,'Reject invalid timeout before execution')
        else:
            runner=Mock(side_effect=subprocess.TimeoutExpired('cmd',.1,output=b'partial'))
            require(m.timed_command('cmd',directory,runner,.1)==result('partial',-1,True),'Keep partial timeout diagnostics'); runner.assert_called_once_with('cmd',directory,timeout=.1)
    elif key == 'budgets':
        usage=dict(steps=0,tokens=0,cost=0,seconds=0); limits=dict(steps=2,tokens=100,cost=.5,seconds=5)
        require(m.remaining_budget(usage,limits) is True,'Allow remaining budget')
        for name in limits:
            if case:
                for invalid in [True,-1,float('nan'),float('inf'),'0']: raises(ValueError,lambda:m.remaining_budget(dict(usage,**{name:invalid}),limits))
            else: raises(m.LimitsExceeded,lambda:m.remaining_budget(dict(usage,**{name:limits[name]}),limits))
    elif key == 'token-usage':
        if case:
            for invalid in [True,-1,1.5,'2']: raises(ValueError,lambda:m.token_usage({'usage':{'prompt_tokens':invalid}}))
            require(m.token_usage({})['total']==0,'Default missing usage')
        else: require(m.token_usage({'usage':{'prompt_tokens':8,'completion_tokens':3}})==dict(input=8,output=3,total=11),'Track input and output tokens')
    elif key == 'output-truncation':
        if case:
            raises(ValueError,lambda:m.truncate_output('x',0)); require(m.truncate_output('123',3)=='123','Preserve output at the boundary')
        else: require(m.truncate_output('123456',3)=='[truncated]\n456','Mark omitted output and retain the tail')
    elif key == 'compaction':
        messages=[dict(role='system',content='rules'),dict(role='user',content='old'),dict(role='assistant',content='old reply'),dict(role='user',content='new'),dict(role='assistant',tool_calls=[call()]),dict(role='tool',tool_call_id='c1',content='evidence')]
        if case:
            raises(ValueError,lambda:m.compact(messages,{},0)); raises(ValueError,lambda:m.compact([],{}))
        else:
            compacted=m.compact(messages,{'goal':'fix'},1)
            require(compacted[0]==messages[0] and compacted[1]['content'].startswith('Working memory (data): ') and 'fix' in compacted[1]['content'] and compacted[2:]==messages[3:],'Keep rules, memory and complete recent tool exchanges')
            compacted[-1]['content']='changed'; require(messages[-1]['content']=='evidence','Copy nested state')
    elif key == 'working-memory':
        if case:
            for goal in ['',None,' ']: raises(ValueError,lambda:m.working_memory(goal))
            raises(ValueError,lambda:m.working_memory('fix',findings=[1]))
        else:
            findings=['failed test']; memory=m.working_memory(' fix ',findings,files=['main.py'],pending=['tests']); findings.append('changed')
            require(memory==dict(goal='fix',findings=['failed test'],changed_files=['main.py'],pending_checks=['tests']),'Record detached structured facts')
            first=m.working_memory('one'); first['findings'].append('x'); require(not m.working_memory('two')['findings'],'Use separate empty defaults')
    elif key == 'trajectory-save':
        path=Path(directory)/'runs'/'session.json'; m.save_session(path,[dict(role='user',content='नमस्ते')],{'goal':'fix'},{'tokens':4})
        data=json.loads(path.read_text(encoding='utf-8')); require(data['schema']=='mini-swe-session-1' and data['messages'][0]['content']=='नमस्ते' and data['usage']['tokens']==4,'Persist complete Unicode evidence')
        if case:
            before=path.read_bytes()
            for value in [object(),float('nan')]:
                raises((ValueError,TypeError),lambda:m.save_session(path,[],{'bad':value},{})); require(path.read_bytes()==before,'Failed serialization preserves the prior file')
    elif key == 'session-restore':
        path=Path(directory)/'saved.json'; data=dict(schema='mini-swe-session-1',messages=[],memory={'goal':'fix'},usage={'tokens':4})
        if case:
            for bad in [dict(data,schema='unknown'),dict(data,messages={}),dict(data,memory=[]),dict(data,usage=[])]:
                path.write_text(json.dumps(bad)); raises(ValueError,lambda:m.restore_session(path))
        else:
            path.write_text(json.dumps(data)); require(m.restore_session(path)==data,'Restore goal, history and counters without resetting')
    elif key == 'filesystem':
        root=Path(directory)
        if case:
            for path in ['../outside',str(root/'absolute'),'.env','.env.local','.git/config','.ssh/id_rsa','.aws/config']: raises(PermissionError,lambda:m.allowed_path(root,path))
            (root/'link').symlink_to(root.parent/'outside',target_is_directory=True); raises(PermissionError,lambda:m.allowed_path(root,'link/secret'))
        else: require(m.allowed_path(root,'src/main.py')==(root/'src/main.py').resolve(),'Resolve a repository-relative path')
    elif key == 'environment-secrets':
        source={'PATH':'/bin','LANG':'C','LC_ALL':'C','API_KEY':'secret','DATABASE_URL':'secret','HOME':'/secret'}
        require(m.safe_environment(source)=={key:source[key] for key in ['PATH','LANG','LC_ALL']},'Allow only explicit non-secret environment keys')
        if case:
            copied=m.safe_environment(source); copied['PATH']='changed'; require(source['PATH']=='/bin' and m.safe_environment({})=={},'Return independent data and handle missing variables')
    elif key == 'network':
        for destination in (['https://example.com','http://127.0.0.1'] if not case else [None,'http://169.254.169.254',{}]): raises(PermissionError,lambda:m.authorize_network(destination))
    elif key == 'approval':
        if case:
            for kind in ['network','unknown','bash','delete']: raises(PermissionError,lambda:m.authorize({'kind':kind},lambda action:False))
            raises(PermissionError,lambda:m.authorize({'kind':'bash'},lambda action:'yes'))
        else:
            require(m.authorize({'kind':'read'},lambda action:False) is True,'Allow a structured read')
            approve=Mock(return_value=True); action={'kind':'bash','command':'pwd'}
            require(m.authorize(action,approve) is True,'Accept explicit approval'); approve.assert_called_once_with(action)
    elif key == 'git-diff':
        runner=Mock(return_value=SimpleNamespace(returncode=1 if case else 0,stdout='- old\n+ new',stderr='not a repository'))
        if case: raises(RuntimeError,lambda:m.inspect_changes(directory,runner))
        else:
            require('+ new' in m.inspect_changes(directory,runner),'Return the actual tracked patch')
            runner.assert_called_once_with(['git','diff','--no-ext-diff','--no-textconv','--','.'],cwd=directory,capture_output=True,text=True,timeout=5)
    else:
        raise AssertionError('Unknown task: '+key)


def run(task_id, add_result, criteria):
    key=task_id.removeprefix('mini-swe-build-')
    for case,criterion in enumerate(criteria):
        try:
            with tempfile.TemporaryDirectory(prefix='mini-swe-task-') as directory:
                check(key,case,directory)
            add_result(criterion,True,'Behavior check passed.')
        except Exception as error:
            add_result(criterion,False,f'{type(error).__name__}: {error}')
