"""
db.py — Database module for Turso (libsql)
Uses Turso HTTP API directly for maximum Vercel compatibility.
"""

import os
import json
import urllib.request

_url = None
_token = None
_initialized = False


def _get_config():
    global _url, _token
    if _url is None:
        url = os.environ.get("TURSO_DATABASE_URL", "")
        _token = os.environ.get("TURSO_AUTH_TOKEN", "")
        if not url or not _token:
            raise RuntimeError(
                "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set."
            )
        if url.startswith("libsql://"):
            url = url.replace("libsql://", "https://", 1)
        _url = url.rstrip("/")
    return _url, _token


def _make_stmt(sql, params=None):
    """Build a pipeline statement dict."""
    if not params:
        return {"type": "execute", "stmt": {"sql": sql}}
    args = []
    for p in params:
        if p is None:
            args.append({"type": "null"})
        elif isinstance(p, int):
            args.append({"type": "integer", "value": str(p)})
        else:
            args.append({"type": "text", "value": str(p)})
    return {"type": "execute", "stmt": {"sql": sql, "args": args}}


def _pipeline(statements):
    """Send multiple statements in a single HTTP request."""
    url, token = _get_config()
    requests_list = statements + [{"type": "close"}]
    body = {"requests": requests_list}

    req = urllib.request.Request(
        f"{url}/v2/pipeline",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    results = []
    for r in data["results"]:
        if r.get("type") == "error":
            raise RuntimeError(f"Turso error: {r['error']['message']}")
        if r.get("type") == "ok":
            result_obj = r.get("response", {}).get("result", {})
            rows_raw = result_obj.get("rows", [])
            rows = []
            for row in rows_raw:
                rows.append(tuple(
                    cell.get("value") if cell.get("type") != "integer"
                    else int(cell["value"])
                    for cell in row
                ))
            results.append(rows)
    return results


def _execute(sql, params=None):
    """Execute a single SQL statement."""
    results = _pipeline([_make_stmt(sql, params)])
    return results[0] if results else []


def _ensure_init():
    """Lazy init — runs once per cold start, single HTTP request."""
    global _initialized
    if _initialized:
        return
    try:
        _pipeline([
            _make_stmt("""
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL DEFAULT 'default',
                    ranking TEXT NOT NULL,
                    client_hash TEXT,
                    expectations TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """),
            _make_stmt("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """),
            _make_stmt("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_active', 'true')"),
        ])
    except RuntimeError:
        pass
    _initialized = True


def init_db():
    _ensure_init()


def is_survey_active() -> bool:
    _ensure_init()
    rows = _execute("SELECT value FROM settings WHERE key = 'is_active'")
    return len(rows) > 0 and rows[0][0] == 'true'


def set_survey_active(active: bool):
    _ensure_init()
    _execute(
        "UPDATE settings SET value = ? WHERE key = 'is_active'",
        ['true' if active else 'false'],
    )


def save_response(ranking_json: str, client_hash: str, expectations: str = None, session_id: str = 'default'):
    _ensure_init()
    rows = _execute(
        "SELECT id FROM responses WHERE client_hash = ? AND session_id = ?",
        [client_hash, session_id],
    )
    if rows:
        _execute(
            "UPDATE responses SET ranking = ?, expectations = ?, created_at = CURRENT_TIMESTAMP WHERE client_hash = ? AND session_id = ?",
            [ranking_json, expectations, client_hash, session_id],
        )
    else:
        _execute(
            "INSERT INTO responses (session_id, ranking, client_hash, expectations) VALUES (?, ?, ?, ?)",
            [session_id, ranking_json, client_hash, expectations],
        )


def get_all_responses(session_id: str = 'default') -> list:
    _ensure_init()
    rows = _execute("SELECT ranking FROM responses WHERE session_id = ?", [session_id])
    return [row[0] for row in rows]


def get_response_count(session_id: str = 'default') -> int:
    _ensure_init()
    rows = _execute("SELECT COUNT(*) FROM responses WHERE session_id = ?", [session_id])
    return rows[0][0] if rows else 0


def get_all_expectations(session_id: str = 'default') -> list:
    _ensure_init()
    rows = _execute(
        "SELECT expectations FROM responses WHERE session_id = ? AND expectations IS NOT NULL AND expectations != ''",
        [session_id],
    )
    return [row[0] for row in rows]


def get_all_responses_full(session_id: str = 'default') -> list:
    _ensure_init()
    rows = _execute(
        "SELECT ranking, expectations FROM responses WHERE session_id = ?",
        [session_id],
    )
    return rows


def get_stats_batch(session_id: str = 'default'):
    """Fetch rankings, expectations, and is_active in a single HTTP request."""
    _ensure_init()
    results = _pipeline([
        _make_stmt("SELECT ranking FROM responses WHERE session_id = ?", [session_id]),
        _make_stmt(
            "SELECT expectations FROM responses WHERE session_id = ? AND expectations IS NOT NULL AND expectations != ''",
            [session_id],
        ),
        _make_stmt("SELECT value FROM settings WHERE key = 'is_active'"),
    ])
    rankings = [row[0] for row in results[0]] if results[0] else []
    expectations = [row[0] for row in results[1]] if results[1] else []
    active = len(results[2]) > 0 and results[2][0][0] == 'true' if results[2] else False
    return rankings, expectations, active


def clear_responses(session_id: str = 'default') -> int:
    _ensure_init()
    count = get_response_count(session_id)
    _execute("DELETE FROM responses WHERE session_id = ?", [session_id])
    return count
