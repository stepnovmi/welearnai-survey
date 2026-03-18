"""
db.py — Database module for Turso (libsql)
Drop-in replacement for aiosqlite. All calls synchronous.
"""

import os

try:
    import libsql_experimental as libsql
except ImportError:
    import libsql

_conn = None


def get_db():
    global _conn
    if _conn is None:
        url = os.environ.get("TURSO_DATABASE_URL")
        token = os.environ.get("TURSO_AUTH_TOKEN")
        if not url or not token:
            raise RuntimeError(
                "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set."
            )
        _conn = libsql.connect(database=url, auth_token=token)
    return _conn


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL DEFAULT 'default',
            ranking TEXT NOT NULL,
            client_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_active', 'true')")
    db.commit()


def is_survey_active() -> bool:
    row = get_db().execute("SELECT value FROM settings WHERE key = 'is_active'").fetchone()
    return row is not None and row[0] == 'true'


def set_survey_active(active: bool):
    get_db().execute("UPDATE settings SET value = ? WHERE key = 'is_active'", ('true' if active else 'false',))
    get_db().commit()


def save_response(ranking_json: str, client_hash: str, session_id: str = 'default'):
    db = get_db()
    existing = db.execute(
        "SELECT id FROM responses WHERE client_hash = ? AND session_id = ?",
        (client_hash, session_id)
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE responses SET ranking = ?, created_at = CURRENT_TIMESTAMP WHERE client_hash = ? AND session_id = ?",
            (ranking_json, client_hash, session_id)
        )
    else:
        db.execute(
            "INSERT INTO responses (session_id, ranking, client_hash) VALUES (?, ?, ?)",
            (session_id, ranking_json, client_hash)
        )
    db.commit()


def get_all_responses(session_id: str = 'default') -> list:
    rows = get_db().execute("SELECT ranking FROM responses WHERE session_id = ?", (session_id,)).fetchall()
    return [row[0] for row in rows]


def get_response_count(session_id: str = 'default') -> int:
    row = get_db().execute("SELECT COUNT(*) FROM responses WHERE session_id = ?", (session_id,)).fetchone()
    return row[0] if row else 0


def clear_responses(session_id: str = 'default') -> int:
    count = get_response_count(session_id)
    get_db().execute("DELETE FROM responses WHERE session_id = ?", (session_id,))
    get_db().commit()
    return count
