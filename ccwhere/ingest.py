"""JSONL ingest: backfill + incremental sync into the event store.

Event-type sets: HANDLED become rows; IGNORED are known non-message types
(verified on real files 2026-07-07) — neither feeds the drift canary.
Anything else is unknown: counted per name, skipped, never fatal.
"""
import json
import re
import shutil
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import db

HANDLED_TYPES = {"user", "assistant"}
IGNORED_TYPES = {
    "queue-operation", "attachment", "file-history-snapshot", "last-prompt",
    "ai-title", "frame-link", "result", "system", "summary", "progress",
    "mode", "custom-title",  # observed in real files, first backfill 2026-07-08
}
KNOWN_USAGE_FIELDS = {
    "input_tokens", "output_tokens", "cache_read_input_tokens",
    "cache_creation_input_tokens", "server_tool_use", "service_tier",
    "cache_creation", "inference_geo", "iterations", "speed",
}
PAIR_CAP_MS = 10 * 60 * 1000  # ponytail: >10min pairs are crashed-session orphans

DEFAULT_PROJECTS_ROOT = Path.home() / ".claude" / "projects"


def _utc(ts: str):
    if not ts:
        return None, None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt = dt.astimezone(timezone.utc)
        return dt.isoformat(), dt.timestamp()
    except ValueError:
        return None, None


_CMD_RE = re.compile(r"<command-name>/?([^<]+)</command-name>")

_CLI_WRAPPERS = {"sudo", "nohup", "time", "command", "exec", "env",
                 "do", "then", "else"}  # shell keywords preceding the program
_CLI_SKIP_SEG = {"cd", "for", "while", "until", "if", "done", "fi", "elif"}


def _cli_program(command):
    """First acting program in a Bash command, or None when unextractable.
    ponytail: naive split, not a shell parser — quoted separators and
    substitutions fall through to None, which classifies as plain Bash."""
    if not command:
        return None
    for seg in re.split(r"\|\||&&|;|\|", command):
        toks = seg.split()
        i = 0
        while i < len(toks) and (re.match(r"^\w+=", toks[i])
                                 or toks[i] in _CLI_WRAPPERS):
            i += 1
        if i < len(toks) and toks[i] == "npx":
            i += 1
            while i < len(toks) and toks[i].startswith("-"):
                i += 1
        elif i + 1 < len(toks) and toks[i] == "pnpm" and toks[i + 1] == "dlx":
            i += 2
        if i >= len(toks):
            continue
        prog = toks[i].rsplit("/", 1)[-1]
        if prog in _CLI_SKIP_SEG:
            continue  # positions or controls flow, doesn't act
        # must look like a program name, not a stray flag or operand
        return prog if re.fullmatch(r"[A-Za-z0-9][\w.+-]*", prog) else None
    return None


_STD_DIRS = ("/bin/", "/usr/bin/", "/sbin/", "/usr/sbin/")
_SHELL_BUILTINS = {"source", "export", "set", "unset", "alias", "eval",
                   "trap", "shift", "read", "wait", "exit", "true", "false",
                   "type", "ulimit", "umask", "printf", "echo", "test"}
_kind_cache = {}


def _cli_kind(prog, which=shutil.which):
    """Provenance split per CONTEXT.md: OS-shipped binaries and shell
    builtins are 'shell' (unprunable, ubiquitous); everything else —
    installed binaries, scripts, programs no longer on PATH — is 'cli'
    (actionable). Machine-derived, never a curated command list."""
    if prog not in _kind_cache:
        if prog in _SHELL_BUILTINS:
            _kind_cache[prog] = "shell"
        else:
            path = which(prog)
            _kind_cache[prog] = ("shell" if path
                                 and path.startswith(_STD_DIRS) else "cli")
    return _kind_cache[prog]


def classify(name: str, tool_input: dict):
    """Consumer classification per CONTEXT.md:
    skill / mcp / cli / shell / builtin."""
    if name == "Skill":
        return "skill", str((tool_input or {}).get("skill", "?")), None
    if name == "Bash":
        prog = _cli_program((tool_input or {}).get("command"))
        if prog:
            return _cli_kind(prog), prog, None
        return "builtin", name, None
    if name.startswith("mcp__"):
        parts = name.split("__")
        server = parts[1] if len(parts) > 1 else name
        tool = "__".join(parts[2:]) if len(parts) > 2 else None
        return "mcp", server, tool
    return "builtin", name, None


def parse_file(path: Path, session_id: str, counters: dict):
    """Yield ('message'|'tool_use'|'tool_result', payload) per recognized event."""
    with open(path, errors="ignore") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                counters["bad_lines"] += 1
                continue
            if e.get("cwd"):
                yield ("cwd", e["cwd"])  # any event type may carry it
            etype = e.get("type")
            counters["total_events"] += 1
            if etype in IGNORED_TYPES:
                continue
            if etype not in HANDLED_TYPES:
                counters["unknown_types"][str(etype)] += 1
                continue
            msg = e.get("message") or {}
            if not isinstance(msg, dict):
                msg = {}
            ts_iso, ts_epoch = _utc(e.get("timestamp", ""))
            usage = msg.get("usage") or {}
            for f in usage:
                if f not in KNOWN_USAGE_FIELDS:
                    counters["unknown_fields"][str(f)] += 1
            yield ("message", {
                "session_id": session_id, "line_no": line_no,
                "uuid": e.get("uuid"), "ts": ts_iso, "role": etype,
                "model": msg.get("model"),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "cache_read_tokens": usage.get("cache_read_input_tokens"),
                "cache_create_tokens": usage.get("cache_creation_input_tokens"),
            })
            content = msg.get("content")
            if etype == "user":
                # typed slash commands: usage evidence for the pruning list,
                # never league consumers (skill-backed ones also fire Skill)
                texts = [content] if isinstance(content, str) else [
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ] if isinstance(content, list) else []
                names = [m for t in texts for m in _CMD_RE.findall(t)]
                for i, name in enumerate(names):
                    yield ("command", {
                        "tool_use_id": f"cmd:{session_id}:{line_no}:{i}",
                        "session_id": session_id, "line_no": line_no,
                        "ts": ts_iso, "consumer": name.strip()})
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    ctype, consumer, mcp_tool = classify(
                        block.get("name", "?"), block.get("input"))
                    yield ("tool_use", {
                        "tool_use_id": block.get("id"),
                        "session_id": session_id, "line_no": line_no,
                        "ts": ts_iso, "ts_epoch": ts_epoch,
                        "tool": block.get("name"),
                        "consumer_type": ctype, "consumer": consumer,
                        "mcp_tool": mcp_tool,
                    })
                elif block.get("type") == "tool_result":
                    yield ("tool_result", {
                        "tool_use_id": block.get("tool_use_id"),
                        "ts_epoch": ts_epoch,
                        "error": 1 if block.get("is_error") else 0,
                    })


def ingest_file(conn, path: Path, project: str, parent_session, counters):
    # Subagent ids repeat across parents (resumed sessions re-run agents) —
    # namespace by parent so twin files never collide on the natural key.
    session_id = f"{parent_session}/{path.stem}" if parent_session else path.stem
    pending = {}   # tool_use_id -> (row, ts_epoch); pairs never span files
    first_ts = last_ts = None
    cwd = None
    added = 0
    for kind, p in parse_file(path, session_id, counters):
        if kind == "cwd":
            cwd = cwd or p
        elif kind == "message":
            conn.execute(
                "INSERT OR REPLACE INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)",
                (p["session_id"], p["line_no"], p["uuid"], p["ts"], p["role"],
                 p["model"], p["input_tokens"], p["output_tokens"],
                 p["cache_read_tokens"], p["cache_create_tokens"]))
            added += 1
            if p["ts"]:
                first_ts = first_ts or p["ts"]
                last_ts = p["ts"]
        elif kind == "command":
            conn.execute(
                "INSERT OR REPLACE INTO tool_calls VALUES "
                "(?,?,?,?,?,?,?,NULL,NULL,NULL)",
                (p["tool_use_id"], p["session_id"], p["line_no"], p["ts"],
                 "command", "command", p["consumer"]))
            added += 1
        elif kind == "tool_use":
            conn.execute(
                "INSERT OR REPLACE INTO tool_calls VALUES (?,?,?,?,?,?,?,?,NULL,NULL)",
                (p["tool_use_id"], p["session_id"], p["line_no"], p["ts"],
                 p["tool"], p["consumer_type"], p["consumer"], p["mcp_tool"]))
            pending[p["tool_use_id"]] = p["ts_epoch"]
            added += 1
        elif kind == "tool_result":
            use_epoch = pending.pop(p["tool_use_id"], None)
            if use_epoch is not None and p["ts_epoch"] is not None:
                dur = int((p["ts_epoch"] - use_epoch) * 1000)
                if 0 <= dur <= PAIR_CAP_MS:
                    conn.execute(
                        "UPDATE tool_calls SET duration_ms=?, error=? "
                        "WHERE tool_use_id=?",
                        (dur, p["error"], p["tool_use_id"]))
    conn.execute(
        "INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?,?)",
        (session_id, project, str(path), parent_session, cwd,
         first_ts, last_ts))
    return added


def discover(projects_root: Path):
    """Yield (path, project, parent_session) for every session file."""
    for path in sorted(projects_root.rglob("*.jsonl")):
        rel = path.relative_to(projects_root)
        project = rel.parts[0]
        parent = None
        if "subagents" in rel.parts:
            parent = rel.parts[rel.parts.index("subagents") - 1]
        yield path, project, parent


def sync(projects_root=None, db_path=None):
    """Backfill/incremental sync. Returns a summary dict; writes a sync_runs row."""
    root = Path(projects_root) if projects_root else DEFAULT_PROJECTS_ROOT
    conn = db.connect(db_path)
    t0 = time.time()
    counters = {"bad_lines": 0, "total_events": 0,
                "unknown_types": Counter(), "unknown_fields": Counter()}
    scanned = parsed = added = 0
    try:
        for path, project, parent in discover(root) if root.exists() else []:
            scanned += 1
            st = path.stat()
            row = conn.execute("SELECT mtime, size FROM sync_state WHERE path=?",
                               (str(path),)).fetchone()
            if row and row[0] == st.st_mtime and row[1] == st.st_size:
                continue
            added += ingest_file(conn, path, project, parent, counters)
            conn.execute(
                "INSERT OR REPLACE INTO sync_state VALUES (?,?,?,?)",
                (str(path), st.st_mtime, st.st_size,
                 datetime.now(timezone.utc).isoformat()))
            parsed += 1
        elapsed_ms = int((time.time() - t0) * 1000)
        summary = {
            "files_scanned": scanned, "files_parsed": parsed,
            "events_added": added, "total_events": counters["total_events"],
            "bad_lines": counters["bad_lines"],
            "unknown_types": dict(counters["unknown_types"]),
            "unknown_fields": dict(counters["unknown_fields"]),
            "elapsed_ms": elapsed_ms,
        }
        conn.execute(
            "INSERT INTO sync_runs (started_at, elapsed_ms, files_scanned,"
            " files_parsed, events_added, total_events, bad_lines,"
            " unknown_types, unknown_fields) VALUES (?,?,?,?,?,?,?,?,?)",
            (datetime.fromtimestamp(t0, timezone.utc).isoformat(), elapsed_ms,
             scanned, parsed, added, counters["total_events"],
             counters["bad_lines"], json.dumps(summary["unknown_types"]),
             json.dumps(summary["unknown_fields"])))
        conn.commit()
        return summary
    finally:
        conn.close()
