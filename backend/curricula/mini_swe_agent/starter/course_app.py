"""A visible integration example for the individual coding-agent tasks."""
import json
import shutil
import tempfile
from pathlib import Path
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Mini-swe repair lab</title>
<style>body{background:#101113;color:#e4e4e7;font:16px/1.7 system-ui;max-width:900px;margin:50px auto;padding:24px}button{font:inherit;padding:10px 18px;background:#b6b3ff;border:0;border-radius:8px;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#191a20;padding:20px;border-radius:8px}small{color:#aaa}</style>
<small>SCRIPTED MODEL · REAL COMMANDS AND TESTS</small><h1>Watch your coding agent repair a bug</h1>
<p>Build the command runner, tool dispatcher and autonomous loop first. This example uses prepared model decisions; the file edits and independent tests execute inside the sandbox.</p>
<button id="run">Run the repair experiment</button><pre id="result">Ready when your components are.</pre>
<script>document.getElementById('run').onclick=async()=>{let b=document.getElementById('run');b.disabled=true;try{let r=await fetch('/api/run',{method:'POST'});document.getElementById('result').textContent=JSON.stringify(await r.json(),null,2)}catch(e){document.getElementById('result').textContent=String(e)}finally{b.disabled=false}}</script></html>'''


@app.get('/')
def index():
    return render_template_string(PAGE)


@app.post('/api/run')
def experiment():
    from phase_autonomy import run_agent
    from phase_shell import execute
    def call(command, ident):
        return {"id": ident, "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": command})}}
    class PreparedModel:
        def __init__(self):
            repair = "python -c \"from pathlib import Path; p=Path('calculator.py'); p.write_text(p.read_text().replace('a - b','a + b'))\""
            self.replies = [
                {"role": "assistant", "tool_calls": [call("cat calculator.py; python -m unittest discover -s .", "inspect")]},
                {"role": "assistant", "tool_calls": [call(repair, "repair")]},
                {"role": "assistant", "content": "Repaired addition. Please verify independently."},
            ]
        def query(self, messages, tools=None):
            return self.replies.pop(0)
    try:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / 'repo'
            shutil.copytree(Path(__file__).parent / 'buggy_repository', repository)
            result = run_agent(PreparedModel(), 'Fix add', str(repository), execute)
            result['verification'] = {'verified': result['verified']}
            return jsonify(result)
    except NotImplementedError:
        return jsonify(error='Complete the shell, tool-calling and autonomous-agent tasks, then retry this example.'), 422
    except Exception as error:
        return jsonify(error=f'{type(error).__name__}: {error}'), 422
