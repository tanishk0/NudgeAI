"""
Deterministic sandbox checks for the "Vulpy Security Review" project.

`VULPY_CHECKS_CODE` is written next to the user's workspace files as
`_vulpy_checks.py` inside the temporary sandbox directory and imported by the
main harness in `verifier.py` for every task id starting with `vulpy-`.

Every check is behavioural first (real exploit payloads are fired at the
user's code) and only falls back to static/AST inspection where behaviour
cannot be observed from the outside (e.g. constant-time comparison, CSPRNG).
Only the Python standard library is used, because the sandbox does not have
Flask / cryptography / PyJWT installed.
"""

VULPY_CHECKS_CODE = r'''
import ast
import base64
import contextlib
import hashlib
import io
import json
import os
import re
import sqlite3
import time
from pathlib import Path

SQL_KEYWORDS = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|WHERE|VALUES)\b", re.IGNORECASE)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exception as exc:  # noqa: BLE001 - we report every failure mode
        return None, f"{type(exc).__name__}: {exc}"


def _quiet(fn, *args, **kwargs):
    """Run fn while swallowing stdout (vulpy's sqlite trace callback is noisy)."""
    with contextlib.redirect_stdout(io.StringIO()):
        return _safe(fn, *args, **kwargs)


def _fresh_db():
    for name in ("db_users.sqlite", "db_posts.sqlite"):
        try:
            os.remove(name)
        except FileNotFoundError:
            pass
    import db_init
    with contextlib.redirect_stdout(io.StringIO()):
        db_init.reset()


def _user_row(username):
    conn = sqlite3.connect("db_users.sqlite")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    finally:
        conn.close()


def _is_sql_literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and bool(SQL_KEYWORDS.search(node.value))


def _sql_string_building_lines(source):
    """Return line numbers where an SQL string is built from dynamic data."""
    tree = ast.parse(source)
    lines = set()
    for node in ast.walk(tree):
        # f"SELECT ... {x}"
        if isinstance(node, ast.JoinedStr):
            has_sql = any(_is_sql_literal(v) for v in node.values)
            has_expr = any(isinstance(v, ast.FormattedValue) for v in node.values)
            if has_sql and has_expr:
                lines.add(node.lineno)
        # "SELECT ... '%s'" % x   or   "SELECT ..." + x
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add)):
            if _is_sql_literal(node.left) or _is_sql_literal(node.right):
                lines.add(node.lineno)
        # "SELECT ... '{}'".format(x)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "format"
            and _is_sql_literal(node.func.value)
        ):
            lines.add(node.lineno)
    return sorted(lines)


def _imports(source):
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _no_user(session):
    return not (isinstance(session, dict) and session.get("username"))


# --------------------------------------------------------------------------
# Task 1 - SQL injection in libuser.py
# --------------------------------------------------------------------------

def check_sqli(add_result, criteria):
    _fresh_db()
    import libuser

    payloads = [
        ("admin' --", "irrelevant"),
        ("' OR '1'='1' --", "x"),
        ("admin", "' OR '1'='1"),
    ]
    bypassed = []
    for user, pw in payloads:
        res, _err = _quiet(libuser.login, user, pw)
        if res:
            bypassed.append(f"login({user!r}, {pw!r}) -> {res!r}")
    c1 = not bypassed
    add_result(
        criteria[0],
        c1,
        "All 3 authentication-bypass payloads were rejected."
        if c1
        else "Authentication bypass succeeded: " + "; ".join(bypassed),
    )

    name, pw = "o'brien", "Gr33n'Tea&Biscuits!"
    _, err_create = _quiet(libuser.create, name, pw)
    logged_in, err_login = _quiet(libuser.login, name, pw)
    row = _user_row(name)
    c2 = err_create is None and err_login is None and logged_in == name and row is not None
    if c2:
        reason = "User `o'brien` with a quote in the password was created and can log in."
    elif err_create:
        reason = f"create(\"o'brien\", ...) crashed - quotes still break the SQL statement ({err_create})."
    elif err_login:
        reason = f"login(\"o'brien\", ...) crashed ({err_login})."
    else:
        reason = f"create/login round-trip failed for a username containing a quote (login returned {logged_in!r})."
    add_result(criteria[1], c2, reason)

    bad_lines = _sql_string_building_lines(_read("libuser.py"))
    c3 = not bad_lines
    add_result(
        criteria[2],
        c3,
        "No SQL statement is built with format()/%/f-strings/+ - every query uses `?` placeholders."
        if c3
        else f"SQL is still assembled from dynamic strings on line(s) {bad_lines} of libuser.py.",
    )


# --------------------------------------------------------------------------
# Task 2 - Plaintext password storage & credential logging
# --------------------------------------------------------------------------

def check_password_storage(add_result, criteria):
    _fresh_db()
    import libuser

    pw = "Tr0ub4dor&3-Horse!"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _, e1 = _safe(libuser.create, "alice", pw)
        _, e2 = _safe(libuser.create, "bob", pw)
        ok_login, e3 = _safe(libuser.login, "alice", pw)
        bad_login, e4 = _safe(libuser.login, "alice", pw + "x")
    logs = buf.getvalue()
    errors = [e for e in (e1, e2, e3, e4) if e]

    ra, rb = _user_row("alice"), _user_row("bob")
    stored_a = str(ra["password"]) if ra is not None else ""
    fast_hashes = {
        hashlib.md5(pw.encode()).hexdigest(),
        hashlib.sha1(pw.encode()).hexdigest(),
        hashlib.sha256(pw.encode()).hexdigest(),
    }
    c1 = ra is not None and bool(stored_a) and pw not in stored_a and stored_a.lower() not in fast_hashes
    if c1:
        reason = "The `password` column holds a derived hash, not the plaintext."
    elif ra is None:
        reason = "User `alice` was not persisted. " + ("; ".join(errors) if errors else "")
    elif stored_a.lower() in fast_hashes:
        reason = "Password stored as an unsalted MD5/SHA digest - crackable with rainbow tables."
    else:
        reason = "The plaintext password is stored in the `password` column."
    add_result(criteria[0], c1, reason)

    stored_b = str(rb["password"]) if rb is not None else ""
    salted = bool(stored_a) and bool(stored_b) and stored_a != stored_b
    c2 = salted and ok_login == "alice" and not bad_login and not errors
    if c2:
        reason = "Identical passwords produce different hashes (per-user salt) and login still verifies correctly."
    elif errors:
        reason = "Exception during create/login: " + "; ".join(errors)
    elif not salted:
        reason = "alice and bob share a password and ended up with the SAME stored value - no per-user random salt."
    elif ok_login != "alice":
        reason = f"login('alice', <correct password>) returned {ok_login!r} - verification against the stored hash is broken."
    else:
        reason = "login('alice', <wrong password>) succeeded!"
    add_result(criteria[1], c2, reason)

    src = _read("libuser.py")
    uses_kdf = ("scrypt" in src) or ("pbkdf2_hmac" in src)
    uses_ct = "compare_digest" in src
    c3 = uses_kdf and uses_ct
    missing = []
    if not uses_kdf:
        missing.append("a slow KDF (`hashlib.scrypt` or `hashlib.pbkdf2_hmac`)")
    if not uses_ct:
        missing.append("constant-time `hmac.compare_digest`")
    add_result(
        criteria[2],
        c3,
        "Uses a memory/CPU-hard KDF and constant-time digest comparison."
        if c3
        else "Missing " + " and ".join(missing) + " in libuser.py.",
    )

    c4 = pw not in logs
    add_result(
        criteria[3],
        c4,
        "No plaintext credentials were written to stdout/logs during create & login."
        if c4
        else "The plaintext password appeared in stdout - `conn.set_trace_callback(print)` (or a print) leaks credentials into logs.",
    )


# --------------------------------------------------------------------------
# Task 3 - Password change flow & password policy
# --------------------------------------------------------------------------

def check_password_change(add_result, criteria):
    _fresh_db()
    import libuser

    strong = "violet-Rocket-Harbor-42!"
    fn = getattr(libuser, "is_password_allowed", None)
    if fn is None:
        add_result(criteria[0], False, "libuser.is_password_allowed() is not defined.")
    else:
        verdicts = {}
        for candidate in ("Sh0rt!", "password1234", "qwertyuiop123", strong):
            res, err = _quiet(fn, candidate)
            verdicts[candidate] = (bool(res), err)
        errs = [e for (_, e) in verdicts.values() if e]
        c1 = (
            not errs
            and not verdicts["Sh0rt!"][0]
            and not verdicts["password1234"][0]
            and not verdicts["qwertyuiop123"][0]
            and verdicts[strong][0]
        )
        if c1:
            reason = "Rejects short (<12) and leaked passwords, accepts a strong passphrase."
        elif errs:
            reason = "is_password_allowed raised: " + "; ".join(errs)
        else:
            reason = "Policy verdicts were wrong: " + ", ".join(
                f"{k!r}->{'allowed' if v[0] else 'rejected'}" for k, v in verdicts.items()
            )
        add_result(criteria[0], c1, reason)

    res, err = _quiet(libuser.password_change, "tim", "wrong-current-password", strong)
    still_old, _ = _quiet(libuser.login, "tim", "12345678")
    took_new, _ = _quiet(libuser.login, "tim", strong)
    c2 = err is None and not res and bool(still_old) and not took_new
    add_result(
        criteria[1],
        c2,
        "Password change was refused when the current password was wrong; tim's password is unchanged."
        if c2
        else (
            f"password_change raised {err}" if err
            else "Changed tim's password WITHOUT verifying the current password (account takeover via stolen session / CSRF)."
        ),
    )

    r_short, e_short = _quiet(libuser.password_change, "tim", "12345678", "123")
    r_leak, e_leak = _quiet(libuser.password_change, "tim", "12345678", "password1234")
    still_old, _ = _quiet(libuser.login, "tim", "12345678")
    c3 = not e_short and not e_leak and not r_short and not r_leak and bool(still_old)
    add_result(
        criteria[2],
        c3,
        "Weak and leaked new passwords were rejected by password_change."
        if c3
        else "password_change accepted a weak/leaked new password (or crashed: "
        + "; ".join(e for e in (e_short, e_leak) if e) + ").",
    )

    r_ok, e_ok = _quiet(libuser.password_change, "tim", "12345678", strong)
    new_ok, _ = _quiet(libuser.login, "tim", strong)
    old_dead, _ = _quiet(libuser.login, "tim", "12345678")
    c4 = e_ok is None and bool(r_ok) and new_ok == "tim" and not old_dead
    add_result(
        criteria[3],
        c4,
        "Valid change returned True; new password works and the old one is dead."
        if c4
        else (
            f"password_change raised {e_ok}" if e_ok
            else f"Happy path broken: returned {r_ok!r}, login(new)={new_ok!r}, login(old)={old_dead!r}."
        ),
    )


# --------------------------------------------------------------------------
# Task 4 - Forgeable session cookie (libsession.py)
# --------------------------------------------------------------------------

def check_session(add_result, criteria):
    import libsession

    src = _read("libsession.py")
    now = int(time.time())

    forged_cookies = [
        base64.b64encode(json.dumps({"username": "admin"}).encode()).decode(),
        base64.urlsafe_b64encode(json.dumps({"username": "admin"}).encode()).decode(),
        base64.urlsafe_b64encode(json.dumps({"username": "admin", "exp": now + 3600}).encode()).decode() + ".AAAA",
    ]
    leaked = []
    for fc in forged_cookies:
        s, _err = _quiet(libsession.load, fc)
        if not _no_user(s):
            leaked.append(fc[:24] + "...")
    c1 = not leaked
    add_result(
        criteria[0],
        c1,
        "Hand-crafted `{\"username\": \"admin\"}` cookies are rejected."
        if c1
        else f"Forged cookie(s) accepted as admin: {leaked} - anyone can impersonate any user.",
    )

    secret = getattr(libsession, "SESSION_SECRET", None)
    strong_secret = secret is not None and len(secret) >= 32 and secret not in ("aaaaaaa", b"aaaaaaa")
    cookie, err_c = _quiet(libsession.create, "elliot")
    roundtrip, err_l = _quiet(libsession.load, cookie) if cookie else (None, "create() returned nothing")
    tamper_ok = True
    if isinstance(cookie, str) and len(cookie) > 8:
        for pos in (len(cookie) // 4, len(cookie) // 2, (3 * len(cookie)) // 4):
            ch = cookie[pos]
            repl = "A" if ch != "A" else "B"
            tampered = cookie[:pos] + repl + cookie[pos + 1:]
            s, _ = _quiet(libsession.load, tampered)
            if not _no_user(s):
                tamper_ok = False
    else:
        tamper_ok = False
    garbage_ok = all(_no_user(_quiet(libsession.load, g)[0]) for g in ("not-a-cookie", "", "....", None))
    roundtrip_ok = isinstance(roundtrip, dict) and roundtrip.get("username") == "elliot"
    c2 = strong_secret and roundtrip_ok and tamper_ok and garbage_ok and not err_c
    if c2:
        reason = "Cookie is HMAC-signed with a strong secret; round-trip works and tampering is detected."
    elif not strong_secret:
        reason = "SESSION_SECRET is missing, shorter than 32 chars/bytes, or still the hard-coded 'aaaaaaa'."
    elif err_c or err_l:
        reason = f"create/load raised: {err_c or err_l}"
    elif not roundtrip_ok:
        reason = f"load(create('elliot')) returned {roundtrip!r} instead of a session for elliot."
    elif not tamper_ok:
        reason = "A cookie with a modified byte was still accepted - signature is not verified."
    else:
        reason = "load() must return {} (not raise) for garbage / empty / None cookies."
    add_result(criteria[1], c2, reason)

    old, e_old = _quiet(libsession.create, "elliot", now=now - 8000)
    fresh, e_fresh = _quiet(libsession.create, "elliot", now=now - 60)
    s_old, _ = _quiet(libsession.load, old, now=now) if old else (None, None)
    s_fresh, _ = _quiet(libsession.load, fresh, now=now) if fresh else (None, None)
    expiry_ok = (
        not e_old and not e_fresh
        and _no_user(s_old)
        and isinstance(s_fresh, dict) and s_fresh.get("username") == "elliot"
    )
    uses_ct = "compare_digest" in src
    c3 = expiry_ok and uses_ct
    if c3:
        reason = "Sessions older than SESSION_TTL are rejected, fresh ones accepted; signature compared in constant time."
    elif e_old or e_fresh:
        reason = f"create(username, now=...) raised: {e_old or e_fresh}"
    elif not expiry_ok:
        reason = "A cookie issued 8000s ago was still accepted (TTL is 7200s) or a fresh cookie was rejected."
    else:
        reason = "Signature is not compared with `hmac.compare_digest`."
    add_result(criteria[2], c3, reason)

    attrs, err_a = _quiet(getattr(libsession, "cookie_attributes", lambda: None))
    attrs = {str(k).lower(): v for k, v in (attrs or {}).items()} if isinstance(attrs, dict) else {}
    samesite = str(attrs.get("samesite") or "").lower()
    c4 = attrs.get("httponly") is True and attrs.get("secure") is True and samesite in ("lax", "strict")
    add_result(
        criteria[3],
        c4,
        "Cookie is HttpOnly, Secure and SameSite - not readable by XSS payloads, not sent cross-site."
        if c4
        else f"cookie_attributes() returned {attrs or err_a!r}; need httponly=True, secure=True, samesite='Lax'|'Strict'.",
    )


# --------------------------------------------------------------------------
# Task 5 - API key issuance & authentication (libapi.py)
# --------------------------------------------------------------------------

def check_api_keys(add_result, criteria):
    _fresh_db()
    import libapi

    src = _read("libapi.py")
    k_none, e_none = _quiet(libapi.keygen, "elliot")
    k_wrong, e_wrong = _quiet(libapi.keygen, "elliot", "nope")
    k_star, e_star = _quiet(libapi.keygen, "*", "x")
    k_ok, e_ok = _quiet(libapi.keygen, "elliot", "123123123")
    c1 = not k_none and not k_wrong and not k_star and isinstance(k_ok, str) and bool(k_ok) and not e_ok
    if c1:
        reason = "Keys are only minted after a successful username + password check."
    elif k_none:
        reason = "keygen('elliot') with NO password returned a valid key - anyone can mint keys for any user."
    elif k_wrong or k_star:
        reason = "keygen accepted a wrong password / wildcard username."
    else:
        reason = f"keygen('elliot', '123123123') did not return a key ({e_ok or k_ok!r})."
    add_result(criteria[0], c1, reason)

    if isinstance(k_ok, str) and k_ok:
        probes = ["*", "?" * len(k_ok), "[0-9a-f]*", "*" + k_ok[-4:], "../*", k_ok[:-1] + "*"]
        bypass = []
        for p in probes:
            who, _ = _quiet(libapi.authenticate, {"X-APIKEY": p})
            if who:
                bypass.append(f"{p!r}->{who!r}")
        legit, e_legit = _quiet(libapi.authenticate, {"X-APIKEY": k_ok})
        missing, _ = _quiet(libapi.authenticate, {})
        c2 = not bypass and legit == "elliot" and not missing
        if c2:
            reason = "Glob/wildcard keys are rejected; the genuine key still authenticates as elliot."
        elif bypass:
            reason = "Wildcard API keys authenticated: " + ", ".join(bypass)
        elif legit != "elliot":
            reason = f"The genuine key no longer authenticates (got {legit!r}{', ' + e_legit if e_legit else ''})."
        else:
            reason = "A request without X-APIKEY header was authenticated."
    else:
        c2, reason = False, "Could not mint a valid key for elliot, so wildcard checks could not run."
    add_result(criteria[1], c2, reason)

    imports = _imports(src)
    k2, _ = _quiet(libapi.keygen, "elliot", "123123123")
    fresh_keys = isinstance(k2, str) and isinstance(k_ok, str) and k2 != k_ok and len(k2) >= 32
    c3 = "random" not in imports and "secrets" in imports and fresh_keys
    if c3:
        reason = "Keys come from the `secrets` CSPRNG, are >=32 chars and unique per issuance."
    elif "random" in imports:
        reason = "`random` (Mersenne Twister) is still imported - its output is predictable after 624 observations."
    elif "secrets" not in imports:
        reason = "Use the `secrets` module (e.g. `secrets.token_hex(32)`) to generate keys."
    else:
        reason = "Two consecutive keys were identical or shorter than 32 characters."
    add_result(criteria[2], c3, reason)

    latest = k2 if isinstance(k2, str) and k2 else k_ok
    exposed = []
    if isinstance(latest, str) and latest:
        needle = latest.encode()
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fname in files:
                if fname.endswith(".py") or fname.endswith(".pyc"):
                    continue
                full = os.path.join(root, fname)
                if latest in fname:
                    exposed.append(f"filename {full}")
                    continue
                try:
                    with open(full, "rb") as fh:
                        if needle in fh.read():
                            exposed.append(f"contents of {full}")
                except OSError:
                    pass
        for name, value in vars(libapi).items():
            if isinstance(value, dict):
                if latest in value or latest in [v for v in value.values() if isinstance(v, str)]:
                    exposed.append(f"module global `{name}`")
            elif isinstance(value, (set, list, tuple)) and latest in value:
                exposed.append(f"module global `{name}`")
        c4 = not exposed
        reason = (
            "Only a digest of the key is stored - a leaked key store cannot be replayed."
            if c4
            else "The raw API key is stored at rest in: " + ", ".join(exposed[:4])
        )
    else:
        c4, reason = False, "No key was issued, so key storage could not be inspected."
    add_result(criteria[3], c4, reason)


# --------------------------------------------------------------------------
# Task 6 - Stored XSS & missing security headers (posts_view.py)
# --------------------------------------------------------------------------

def check_xss(add_result, criteria):
    import posts_view as pv

    posts = [
        {"text": "<script>alert(document.cookie)</script>"},
        {"text": "<img src=x onerror=alert(1)>"},
        {"text": "Fish & Chips"},
    ]
    html_out, err = _quiet(pv.render_posts, "elliot", posts)
    low = (html_out or "").lower()
    c1 = (
        not err
        and "<script" not in low
        and "<img" not in low
        and "&lt;script&gt;" in (html_out or "")
        and "Fish &amp; Chips" in (html_out or "")
    )
    if c1:
        reason = "Post bodies are HTML-escaped: payloads render as inert text, `&` becomes `&amp;`."
    elif err:
        reason = f"render_posts raised {err}"
    elif "<script" in low or "<img" in low:
        reason = "Stored XSS: raw <script>/<img onerror> from a post body reached the HTML output (the `| safe` bug)."
    else:
        reason = "Payload was stripped instead of escaped, or legitimate text ('Fish & Chips') is not rendered as `Fish &amp; Chips`."
    add_result(criteria[0], c1, reason)

    h2, e_h2 = _quiet(pv.render_posts, '"><svg onload=alert(1)>', [])
    link, e_link = _quiet(pv.render_user_link, 'x" onmouseover="alert(1)')
    c2 = (
        not e_h2 and not e_link
        and "<svg" not in (h2 or "").lower()
        and 'x" onmouseover' not in (link or "")
        and "<a" in (link or "")
    )
    add_result(
        criteria[1],
        c2,
        "Usernames are escaped in both element text and the href attribute (quotes included)."
        if c2
        else (
            f"Raised: {e_h2 or e_link}" if (e_h2 or e_link)
            else "A crafted username broke out of the heading or the href attribute (escape quotes with `html.escape(s, quote=True)`)."
        ),
    )

    headers, e_hdr = _quiet(pv.security_headers)
    hdr = {str(k).lower(): str(v) for k, v in (headers or {}).items()} if isinstance(headers, dict) else {}
    csp = hdr.get("content-security-policy", "")
    csp_ok = ("default-src 'self'" in csp or "script-src 'self'" in csp) and "unsafe-inline" not in csp and "unsafe-eval" not in csp
    nosniff = hdr.get("x-content-type-options", "").lower() == "nosniff"
    framing = hdr.get("x-frame-options", "").upper() in ("DENY", "SAMEORIGIN") or "frame-ancestors" in csp
    c3 = csp_ok and nosniff and framing
    problems = []
    if not csp_ok:
        problems.append("a CSP with `default-src 'self'`/`script-src 'self'` and no unsafe-inline/unsafe-eval")
    if not nosniff:
        problems.append("`X-Content-Type-Options: nosniff`")
    if not framing:
        problems.append("clickjacking protection (`X-Frame-Options: DENY` or CSP `frame-ancestors`)")
    add_result(
        criteria[2],
        c3,
        "Defense-in-depth headers present: strict CSP, nosniff, anti-framing."
        if c3
        else "security_headers() is missing " + "; ".join(problems) + (f" (raised {e_hdr})" if e_hdr else "."),
    )


CHECKS = {
    "vulpy-task-1-sqli": check_sqli,
    "vulpy-task-2-password-storage": check_password_storage,
    "vulpy-task-3-password-change": check_password_change,
    "vulpy-task-4-session-forgery": check_session,
    "vulpy-task-5-api-keys": check_api_keys,
    "vulpy-task-6-xss-headers": check_xss,
}


def run(task_id, add_result, criteria):
    CHECKS[task_id](add_result, criteria)
'''

