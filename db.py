"""
db.py — Database module for Turso (libsql)
Uses Turso HTTP API directly for maximum Vercel compatibility.
"""

import os
import json
import urllib.request
import urllib.error

_url = None
_token = None


def _get_config():
    global _url, _token
    if _url is None:
        url = os.environ.get("TURSO_DATABASE_URL", "")
        _token = os.environ.get("TURSO_AUTH_TOKEN", "")
        if not url or not _token:
            raise RuntimeError(
                "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set."
            )
        # Convert libsql:// to https://
        if url.startswith("libsql://"):
            url = url.replace("libsql://", "https://", 1)
        _url = url.rstrip("/")
    return _url, _token


def _execute(sql, params=None):
    """Execute a SQL statement via Turso HTTP API v2 (pipeline)."""
    url, token = _get_config()

    if params:
        args = [{"type": "text", "value": str(p)} for p in params]
        stmt = {"type": "execute", "stmt": {"sql": sql, "args": args}}
    else:
        stmt = {"type": "execute", "stmt": {"sql": sql}}

    body = {"requests": [stmt, {"type": "close"}]}

    req = urllib.request.Request(
        f"{url}/v2/pipeline",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    result = data["results"][0]
    if result["type"] == "error":
        raise RuntimeError(f"Turso error: {result['error']['message']}")

    response = result.get("response", {})
    result_obj = response.get("result", {})
    cols = result_obj.get("cols", [])
    rows_raw = result_obj.get("rows", [])

    rows = []
    for row in rows_raw:
        rows.append(tuple(
            cell.get("value") if cell.get("type") != "integer"
            else int(cell["value"])
            for cell in row
        ))

    return rows


def init_db():
    _execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL DEFAULT 'default',
            ranking TEXT NOT NULL,
            client_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    _execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_active', 'true')")


def is_survey_active() -> bool:
    rows = _execute("SELECT value FROM settings WHERE key = 'is_active'")
    return len(rows) > 0 and rows[0][0] == 'true'


def set_survey_active(active: bool):
    _execute(
        "UPDATE settings SET value = ? WHERE key = 'is_active'",
        ['true' if active else 'false'],
    )


def save_response(ranking_json: str, client_hash: str, session_id: str = 'default'):
    rows = _execute(
        "SELECT id FROM responses WHERE client_hash = ? AND session_id = ?",
        [client_hash, session_id],
    )
    if rows:
        _execute(
            "UPDATE responses SET ranking = ?, created_at = CURRENT_TIMESTAMP WHERE client_hash = ? AND session_id = ?",
            [ranking_json, client_hash, session_id],
        )
    else:
        _execute(
            "INSERT INTO responses (session_id, ranking, client_hash) VALUES (?, ?, ?)",
            [session_id, ranking_json, client_hash],
        )


def get_all_responses(session_id: str = 'default') -> list:
    rows = _execute("SELECT ranking FROM responses WHERE session_id = ?", [session_id])
    return [row[0] for row in rows]


def get_response_count(session_id: str = 'default') -> int:
    rows = _execute("SELECT COUNT(*) FROM responses WHERE session_id = ?", [session_id])
    return rows[0][0] if rows else 0


def clear_responses(session_id: str = 'default') -> int:
    count = get_response_count(session_id)
    _execute("DELETE FROM responses WHERE session_id = ?", [session_id])
    return count
