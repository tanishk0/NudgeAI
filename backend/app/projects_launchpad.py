"""A complete, runnable building project with small, behavior-checked tasks."""
from app.models import Project, ProjectFile, TaskItem

STORE = '''import sqlite3
from urllib.parse import urlparse

DB_PATH = "reading-list.sqlite3"

def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def init_db():
    # Task 1: create the links table without deleting existing data.
    pass

def list_links(query=""):
    # Task 2: return dictionaries ordered by newest id first.
    # Task 7: filter titles when query is supplied.
    return []

def valid_url(url):
    # Task 3: accept only absolute HTTP(S) URLs with a hostname.
    return False

def add_link(title, url):
    # Task 4: validate, insert using placeholders, return the inserted dictionary.
    raise NotImplementedError("Build add_link in Task 4")

def toggle_read(link_id):
    # Task 5: toggle is_read and return the updated dictionary, or None if missing.
    raise NotImplementedError("Build toggle_read in Task 5")

def delete_link(link_id):
    # Task 6: delete one link and return True if it existed.
    raise NotImplementedError("Build delete_link in Task 6")

def stats():
    # Task 8: return total, read, and unread counts.
    return {"total": 0, "read": 0, "unread": 0}
'''

APP = '''from flask import Flask, jsonify, render_template, request
import store

app = Flask(__name__)
store.init_db()

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/links")
def links():
    return jsonify(store.list_links(request.args.get("q", "")))

@app.post("/api/links")
def create():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(store.add_link(data.get("title", ""), data.get("url", ""))), 201
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except NotImplementedError as exc:
        return jsonify(error=str(exc)), 501

@app.patch("/api/links/<int:link_id>")
def toggle(link_id):
    try:
        item = store.toggle_read(link_id)
        return (jsonify(item), 200) if item else (jsonify(error="Link not found"), 404)
    except NotImplementedError as exc:
        return jsonify(error=str(exc)), 501

@app.delete("/api/links/<int:link_id>")
def delete(link_id):
    try:
        return ("", 204) if store.delete_link(link_id) else (jsonify(error="Link not found"), 404)
    except NotImplementedError as exc:
        return jsonify(error=str(exc)), 501

@app.get("/api/stats")
def stats():
    return jsonify(store.stats())
'''

HTML = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DevShelf · Your reading list</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f6f8;color:#242630;font-family:system-ui,sans-serif}main{max-width:800px;margin:0 auto;padding:48px 24px}header{display:flex;justify-content:space-between;align-items:center}.brand{font-size:22px;font-weight:750;letter-spacing:-.7px;color:#6550bc}.tag{font-size:11px;color:#91889f;border:1px solid #ddd8eb;padding:5px 8px;border-radius:6px}h1{font-size:35px;letter-spacing:-1.3px;margin:35px 0 8px}p{color:#84808d;font-size:14px;line-height:1.8}.stats{display:flex;gap:12px;margin:24px 0}.stats>span{background:white;border:1px solid #e9e6ef;padding:12px 18px;border-radius:9px;color:#8b8499;font-size:12px}.stats b{color:#67568f;margin-right:6px}form{display:flex;gap:9px;flex-wrap:wrap;background:white;padding:18px;border:1px solid #e9e6ef;border-radius:11px}input{font:inherit;font-size:13px;border:1px solid #e7e3ef;border-radius:6px;padding:10px 12px;background:white;min-width:0;flex:1}input:focus{outline:2px solid #d7ccec}button{cursor:pointer;border:0;background:#7960c5;color:white;border-radius:6px;padding:10px 15px;font:inherit;font-size:12px}button:hover{opacity:.85}#search{width:100%;margin:22px 0 12px}.link{display:flex;gap:12px;align-items:center;background:white;padding:17px;margin:9px 0;border:1px solid #e9e6ef;border-radius:9px}.link>div{flex:1;min-width:0}.link a{color:#504060;font-size:14px;text-decoration:none;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.link small{display:block;color:#a29ba9;font-size:11px;margin-top:5px}.link button{padding:5px 9px;background:#eee9f7;color:#8975ae}.link.read a{text-decoration:line-through;color:#b0a7bb}#empty{text-align:center;padding:35px 10px;background:#eeebf3;border:1px dashed #d9d2e4;border-radius:9px;color:#91889e}#error{color:#b65e6d;font-size:13px;min-height:18px;margin-top:13px}footer{margin-top:30px;color:#aba4b4;font-size:11px}label{font-size:12px;color:#9b90aa}
</style></head><body><main><header><span class="brand">▤ DevShelf</span><span class="tag">BUILT BY YOU</span></header><h1>Good reads. Great ideas.</h1><p>A little home for the articles, docs, and ideas you want to come back to.</p><div class="stats"><span><b id="total">0</b> saved</span><span><b id="read">0</b> read</span><span><b id="unread">0</b> to explore</span></div><form id="add"><input id="title" aria-label="Article title" placeholder="Give it a title" required maxlength="200"><input id="url" aria-label="Article URL" placeholder="https://something-worth-reading.com" required><button>Save link</button></form><div id="error" role="alert"></div><input id="search" aria-label="Search saved links" placeholder="Search your shelf…"><div id="links"></div><div id="empty">Your next great read belongs here.<p>Save your first link to start your collection.</p></div><footer>Your learning project · Python, Flask & SQLite</footer></main><script>
const error=document.getElementById('error');
async function api(path,options){const r=await fetch(path,options);if(!r.ok){let data={};try{data=await r.json()}catch{}throw new Error(data.error||'Request failed')}return r.status===204?null:r.json()}
async function load(){try{const links=await api('/api/links?q='+encodeURIComponent(document.getElementById('search').value));const root=document.getElementById('links');root.replaceChildren();document.getElementById('empty').hidden=links.length>0;links.forEach(link=>{const row=document.createElement('article');row.className='link'+(link.is_read?' read':'');const toggle=document.createElement('button');toggle.textContent=link.is_read?'✓':'○';toggle.setAttribute('aria-label','Toggle read status');toggle.onclick=()=>action('/api/links/'+link.id,'PATCH');const content=document.createElement('div');const anchor=document.createElement('a');anchor.textContent=link.title;anchor.href=link.url;anchor.target='_blank';anchor.rel='noopener noreferrer';const detail=document.createElement('small');detail.textContent=link.url;content.append(anchor,detail);const remove=document.createElement('button');remove.textContent='Remove';remove.onclick=()=>action('/api/links/'+link.id,'DELETE');row.append(toggle,content,remove);root.append(row)});const s=await api('/api/stats');for(const key of ['total','read','unread'])document.getElementById(key).textContent=s[key]}catch(e){error.textContent=e.message}}
async function action(path,method){try{await api(path,{method});error.textContent='';await load()}catch(e){error.textContent=e.message}}
document.getElementById('add').onsubmit=async e=>{e.preventDefault();try{await api('/api/links',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:document.getElementById('title').value,url:document.getElementById('url').value})});e.target.reset();error.textContent='';await load()}catch(e){error.textContent=e.message}};
document.getElementById('search').oninput=()=>load();load();
</script></body></html>'''

SPECS = [
    ("schema", "Create the database schema", "Create a links table that survives repeated initialization.", "Implement init_db() using CREATE TABLE IF NOT EXISTS. Columns: id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0. Use connect() and commit the transaction.", ["The links table has the required columns", "Repeated initialization preserves existing links"], "A schema is a contract for every feature that follows. What should happen when the application starts twice?"),
    ("list", "Read your saved links", "Return saved links as dictionaries, newest first.", "Implement list_links(query=''). Read all rows ordered by id DESC and return a list of dictionaries with id, title, url, and is_read. An empty database should return []. Search is added in Task 7.", ["An empty shelf returns an empty list", "Saved links are dictionaries ordered newest first"], "sqlite3.Row can be converted to a dictionary. Which ORDER BY expression puts the newest id first?"),
    ("urls", "Validate links at the boundary", "Accept only absolute HTTP and HTTPS URLs.", "Implement valid_url(url). Return False for non-strings, blank values, javascript:, file:, relative paths, or URLs without a hostname. Parse with urllib.parse.urlparse; require scheme http or https and a valid hostname. Do not make network requests.", ["Absolute HTTP and HTTPS URLs are accepted", "Unsafe schemes, relative URLs, and missing hosts are rejected"], "A URL has a scheme and a network location. Which of those should this application trust?"),
    ("create", "Save a link", "Validate input and persist a new reading-list entry.", "Implement add_link(title, url). Strip surrounding whitespace. Require a nonempty title of at most 200 characters and a URL accepted by valid_url. Raise ValueError for bad input. Use parameterized SQL, commit, and return the inserted row as a dictionary. Try Save link in Preview.", ["Valid input is trimmed and persisted", "Blank, overlong, and unsafe input is rejected", "Quotes are stored as data without damaging the schema"], "Validate before opening a write transaction. The cursor's lastrowid identifies your new row."),
    ("toggle", "Track what you’ve read", "Toggle a saved link between read and unread.", "Implement toggle_read(link_id). Flip is_read between 0 and 1, commit, and return the updated dictionary. Return None when the id does not exist. Click the circle next to a link in Preview to try it.", ["A link toggles from unread to read and back", "A missing link returns None without changing other rows"], "You can perform the toggle atomically in SQL using 1 - is_read."),
    ("delete", "Remove a saved link", "Delete exactly one requested link.", "Implement delete_link(link_id). Use a parameterized DELETE, commit, and return True if a row was removed, otherwise False. Removing one link must preserve all other links.", ["Deleting a link removes only that row", "Deleting a missing id returns False"], "cursor.rowcount tells you whether a DELETE affected a record."),
    ("search", "Find a title on your shelf", "Filter saved links by a case-insensitive title substring.", "Extend list_links(query=''). Trim query whitespace. Empty search still returns all rows. Otherwise return rows whose title contains the query, case-insensitively, ordered by id DESC. Bind values rather than interpolating SQL. The search box is already connected.", ["Search matches title substrings without case sensitivity", "Empty search returns every row and quote input stays safe"], "LOWER and instr can express literal substring matching without treating % and _ as wildcards."),
    ("stats", "Show a useful progress summary", "Compute total, read, and unread counts from persisted rows.", "Implement stats() returning {'total': int, 'read': int, 'unread': int}. An empty shelf returns zero for each count. Counts must reflect toggles and deletes. Refresh Preview and see your completed application.", ["An empty shelf reports zero counts", "Counts reflect read status and deletion"], "COUNT and SUM can answer this in one query. How will you handle SUM returning NULL for an empty table?"),
]

LAUNCHPAD_PROJECT = Project(id="build-devshelf", title="Build DevShelf: Your Developer Reading List",
    subtitle="Build a real app, one small feature at a time. Save good reads, track progress, and find ideas again.",
    difficulty="Beginner", category="Full-stack Foundations", tags=["Python", "Flask", "SQLite", "APIs", "Validation"], estimated_minutes=100,
    problem_statement="Developers collect articles and documentation across dozens of tabs. Build a small reading-list application that stores links, tracks read status, supports search, and summarizes progress. The interface and API routes are scaffolded; you build the data layer that makes them work.",
    system_context="Browser UI → Flask JSON routes → store.py → SQLite. Routes translate validation errors into HTTP 400 and missing resources into HTTP 404. Work stays inside an isolated runtime; exported files can run locally with Flask.",
    ai_failure_mode="A working interface can hide an unfinished backend. Reliable applications validate input, preserve data, use parameterized queries, and handle empty and missing records deliberately.",
    technologies=["Python", "Flask", "SQLite", "HTML / CSS", "Fetch API"], learning_outcomes=["Design and initialize a persistent database schema", "Implement a CRUD data layer behind a JSON API", "Validate input and use parameterized SQL", "Build search and aggregate statistics", "Verify behavior and inspect the running application"],
    prerequisites=["Python functions and dictionaries", "Basic SQL is helpful; hints explain each query"], deliverable="A runnable reading-list web app with link creation, read tracking, deletion, search, and a live progress summary.",
    runtime={"entrypoint":"app.py","mode":"web","port":5000,"path":"/"},
    starter_files=[ProjectFile(path="store.py",language="python",content=STORE), ProjectFile(path="app.py",language="python",content=APP,read_only=True), ProjectFile(path="templates/index.html",language="html",content=HTML), ProjectFile(path="requirements.txt",language="plaintext",content="Flask==3.1.2\n",read_only=True), ProjectFile(path="README.md",language="markdown",content="# DevShelf\n\nBuild the data layer in store.py. Use Run for Preview and Check task for acceptance tests.\n\n## Run your export locally\n\npip install -r requirements.txt\npython -m flask --app app run\n\nThe preview database is temporary. Restarting the isolated runtime starts with a fresh database; your source files remain saved.\n",read_only=True)],
    tasks=[TaskItem(id=f"devshelf-{key}", order=index+1, title=title, category="architecture" if key in {"schema","list","stats"} else "security" if key=="urls" else "debugging", objective=objective, instructions=instructions, validation_criteria=criteria, hints=[hint], target_file="store.py", mentor_context="This is a building exercise. Teach the data-layer concept and its observable UI behavior. Read app.py and the schema before proposing changes. Existing routes and UI are wired already; focus on the current store.py function.") for index,(key,title,objective,instructions,criteria,hint) in enumerate(SPECS)])

CHECKS = r'''
import sqlite3
import store

def run(task_id, add_result, criteria):
    store.DB_PATH = "checks.sqlite3"
    store.init_db()
    def seed(title="Python docs", url="https://docs.python.org", is_read=0):
        with store.connect() as connection:
            cursor=connection.execute("INSERT INTO links (title,url,is_read) VALUES (?,?,?)",(title,url,is_read))
            return cursor.lastrowid
    key=task_id.removeprefix("devshelf-")
    if key=="schema":
        with store.connect() as c:
            columns={r[1] for r in c.execute("PRAGMA table_info(links)")}
        add_result(criteria[0], {"id","title","url","is_read"}<=columns, "Check the schema's four required columns.")
        item=seed();store.init_db()
        with store.connect() as c: exists=c.execute("SELECT COUNT(*) FROM links WHERE id=?",(item,)).fetchone()[0]==1
        add_result(criteria[1],exists,"Initialization must not clear saved data.")
    elif key=="list":
        add_result(criteria[0],store.list_links()==[],"An empty shelf is a normal state.")
        first=seed();second=seed("Flask docs")
        rows=store.list_links()
        add_result(criteria[1],len(rows)==2 and all(isinstance(r,dict) and {"id","title","url","is_read"}<=r.keys() for r in rows) and [r["id"] for r in rows]==[second,first],"Return dictionaries ordered by descending id.")
    elif key=="urls":
        add_result(criteria[0],all(store.valid_url(u) is True for u in ["https://example.com/docs?q=python","http://localhost:3000"]),"Accept absolute HTTP(S) links.")
        add_result(criteria[1],all(store.valid_url(u) is False for u in [None,42,""," ","/docs","javascript:alert(1)","file:///etc/passwd","https:///missing","https://"]),"Reject invalid types, schemes and missing hosts.")
    elif key=="create":
        item=store.add_link("  Python  ","  https://python.org  ")
        with store.connect() as c: row=c.execute("SELECT * FROM links WHERE id=?",(item["id"],)).fetchone()
        add_result(criteria[0],isinstance(item,dict) and row["title"]=="Python" and row["url"]=="https://python.org" and row["is_read"]==0,"Trim values, commit, and return the inserted row.")
        rejected=0
        for title,url in [(" ","https://x.com"),("x"*201,"https://x.com"),("x","javascript:alert(1)"),(None,"https://x.com")]:
            try:store.add_link(title,url)
            except ValueError:rejected+=1
        add_result(criteria[1],rejected==4,"Reject invalid values with ValueError.")
        title="O'Brien'); DROP TABLE links; --"
        item=store.add_link(title,"https://example.com")
        with store.connect() as c: row=c.execute("SELECT title FROM links WHERE id=?",(item["id"],)).fetchone()
        add_result(criteria[2],row["title"]==title,"Quotes must round-trip without changing SQL structure.")
    elif key=="toggle":
        item=seed();one=store.toggle_read(item);two=store.toggle_read(item)
        add_result(criteria[0],one["is_read"]==1 and two["is_read"]==0,"Both toggle directions must work.")
        add_result(criteria[1],store.toggle_read(9999) is None,"A missing id is not an exception.")
    elif key=="delete":
        first=seed();second=seed("Keep me")
        deleted=store.delete_link(first)
        with store.connect() as c: ids=[r[0] for r in c.execute("SELECT id FROM links")]
        add_result(criteria[0],deleted is True and ids==[second],"Only the requested row should be removed.")
        add_result(criteria[1],store.delete_link(9999) is False,"Missing id returns False.")
    elif key=="search":
        first=seed("Python patterns");second=seed("PYTHON reference");seed("Flask handbook")
        add_result(criteria[0],[r["id"] for r in store.list_links("  pYtHoN  ")]==[second,first],"Match titles case-insensitively and preserve ordering.")
        seed("O'Brien")
        add_result(criteria[1],len(store.list_links(" "))==4 and len(store.list_links("O'Brien"))==1 and store.list_links("%' OR 1=1 --")==[],"Blank search shows all; quoted search stays literal.")
    elif key=="stats":
        add_result(criteria[0],store.stats()=={"total":0,"read":0,"unread":0},"Use zero counts for an empty shelf.")
        seed();first=seed("Read me",is_read=1);seed("Another read",is_read=1)
        before=store.stats();store.toggle_read(first);store.delete_link(first)
        add_result(criteria[1],before=={"total":3,"read":2,"unread":1} and store.stats()=={"total":2,"read":1,"unread":1},"Counts must reflect persisted changes.")
'''

SOLVED_STORE = '''import sqlite3
from urllib.parse import urlparse
DB_PATH = "reading-list.sqlite3"

def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def init_db():
    with connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS links (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0)")

def list_links(query=""):
    with connect() as c:
        return [dict(row) for row in c.execute("SELECT * FROM links WHERE instr(lower(title), lower(?)) > 0 ORDER BY id DESC", (query.strip(),))]

def valid_url(url):
    if not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.hostname) and not any(ch.isspace() for ch in parsed.netloc)
    except ValueError:
        return False

def add_link(title, url):
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200 or not valid_url(url):
        raise ValueError("Use a title of 1–200 characters and an absolute HTTP(S) URL.")
    with connect() as c:
        cursor = c.execute("INSERT INTO links (title, url) VALUES (?, ?)", (title.strip(), url.strip()))
        return dict(c.execute("SELECT * FROM links WHERE id = ?", (cursor.lastrowid,)).fetchone())

def toggle_read(link_id):
    with connect() as c:
        c.execute("UPDATE links SET is_read = 1 - is_read WHERE id = ?", (link_id,))
        row = c.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
        return dict(row) if row else None

def delete_link(link_id):
    with connect() as c:
        return c.execute("DELETE FROM links WHERE id = ?", (link_id,)).rowcount > 0

def stats():
    with connect() as c:
        total, read = c.execute("SELECT COUNT(*), COALESCE(SUM(is_read), 0) FROM links").fetchone()
        return {"total": total, "read": read, "unread": total - read}
'''

def reference_solutions():
    import ast
    functions = {node.name: ast.get_source_segment(SOLVED_STORE, node) for node in ast.parse(SOLVED_STORE).body if isinstance(node, ast.FunctionDef)}
    names = {"schema":"init_db", "list":"list_links", "urls":"valid_url", "create":"add_link", "toggle":"toggle_read", "delete":"delete_link", "search":"list_links", "stats":"stats"}
    result = {f"devshelf-{key}": "```python\n" + functions[name] + "\n```" for key,name in names.items()}
    result["devshelf-list"] = '```python\ndef list_links(query=""):\n    with connect() as c:\n        return [dict(row) for row in c.execute("SELECT * FROM links ORDER BY id DESC")]\n```'
    return result
