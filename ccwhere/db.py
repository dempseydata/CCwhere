"""SQLite schema + connection. One file, WAL, no rollup tables —
all aggregation happens at query time (see design.md)."""
import json
import sqlite3
from pathlib import Path

DEFAULT_DB = Path.home() / ".ccwhere" / "ccwhere.db"

SCHEMA_VERSION = "7"  # v7: flag tokens no longer misread as cli programs

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY, value TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  session_id     TEXT PRIMARY KEY,
  project        TEXT,
  file           TEXT,
  parent_session TEXT,
  cwd            TEXT,
  first_ts       TEXT,
  last_ts        TEXT
);
CREATE TABLE IF NOT EXISTS messages (
  session_id          TEXT NOT NULL,
  line_no             INTEGER NOT NULL,
  uuid                TEXT,
  ts                  TEXT,
  role                TEXT,
  model               TEXT,
  input_tokens        INTEGER,
  output_tokens       INTEGER,
  cache_read_tokens   INTEGER,
  cache_create_tokens INTEGER,
  PRIMARY KEY (session_id, line_no)
);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages (ts);
CREATE TABLE IF NOT EXISTS tool_calls (
  tool_use_id   TEXT PRIMARY KEY,
  session_id    TEXT NOT NULL,
  line_no       INTEGER,
  ts            TEXT,
  tool          TEXT,
  consumer_type TEXT,
  consumer      TEXT,
  mcp_tool      TEXT,
  duration_ms   INTEGER,
  error         INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_consumer ON tool_calls (consumer, ts);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls (session_id);
CREATE TABLE IF NOT EXISTS sync_state (
  path      TEXT PRIMARY KEY,
  mtime     REAL,
  size      INTEGER,
  synced_at TEXT
);
CREATE TABLE IF NOT EXISTS sync_runs (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at     TEXT,
  elapsed_ms     INTEGER,
  files_scanned  INTEGER,
  files_parsed   INTEGER,
  events_added   INTEGER,
  total_events   INTEGER,
  bad_lines      INTEGER,
  unknown_types  TEXT,
  unknown_fields TEXT
);
"""


def _overrides_path(db_path=None):
    # lives beside the db but is NOT part of the disposable cache:
    # operator curation must survive schema rebuilds
    return (Path(db_path).parent if db_path else DEFAULT_DB.parent) \
        / "overrides.json"


def load_overrides(db_path=None) -> set:
    """Operator-demoted cli consumers. Missing/corrupt file → empty set."""
    try:
        data = json.loads(_overrides_path(db_path).read_text())
        return {str(c) for c in data.get("demoted", [])}
    except (OSError, ValueError):
        return set()


def save_overrides(demoted, db_path=None):
    p = _overrides_path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"demoted": sorted(demoted)}, indent=1))


def connect(db_path=None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    # The store is a disposable cache of JSONL truth: on schema mismatch,
    # delete and rebuild (full backfill ~1.3s). No migrations in v1.
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row and row[0] != SCHEMA_VERSION:
            conn.close()
            for suffix in ("", "-wal", "-shm"):
                Path(str(path) + suffix).unlink(missing_ok=True)
            conn = sqlite3.connect(path)
    except sqlite3.OperationalError:
        pass  # fresh database, no meta table yet
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('schema_version', ?)",
                 (SCHEMA_VERSION,))
    conn.commit()
    return conn
