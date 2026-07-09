"""Read-only liveness: what is running right now, from disk truth.
Deliberately bypasses the store — "what is running" must not depend on
when the operator last synced (live-view spec)."""
import json
import subprocess
import time
from pathlib import Path

from .ingest import DEFAULT_PROJECTS_ROOT

LIVE_WINDOW_S = 5 * 60      # decided at definition
RECENT_WINDOW_S = 15 * 60   # "recently active" band (operator, 2026-07-08)
TAIL_BYTES = 64 * 1024      # bounded read: last events only


def _tail_event(path):
    """Last parseable event in a file; malformed tail lines skipped."""
    try:
        with open(path, "rb") as fh:
            size = fh.seek(0, 2)
            fh.seek(max(size - TAIL_BYTES, 0))
            lines = fh.read().split(b"\n")
    except OSError:
        return {}
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("type"):
            return e
    return {}


def _activity(e):
    msg = e.get("message") or {}
    content = msg.get("content") if isinstance(msg, dict) else None
    if e.get("type") == "assistant":
        if isinstance(content, list):
            tools = [b.get("name") for b in content
                     if isinstance(b, dict) and b.get("type") == "tool_use"]
            if tools:
                return f"running {tools[-1]}"
        return "assistant responding"
    if e.get("type") == "user":
        if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result"
                for b in content):
            return "tool result returned"
        return "user prompt"
    return str(e.get("type"))


def live_sessions(projects_root=None, now=None):
    """One row per live session, freshest first. Subagents roll up."""
    root = Path(projects_root) if projects_root else DEFAULT_PROJECTS_ROOT
    now = now or time.time()
    out = {}
    if not root.exists():
        return []
    for path in root.rglob("*.jsonl"):
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue
        if age > RECENT_WINDOW_S:
            continue
        rel = path.relative_to(root)
        session = rel.parts[rel.parts.index("subagents") - 1] \
            if "subagents" in rel.parts else path.stem
        e = _tail_event(path)
        msg = e.get("message") if isinstance(e.get("message"), dict) else {}
        cur = out.get(session)
        if cur is None or age < cur["age_s"]:
            out[session] = {"session": session, "project": rel.parts[0],
                            "model": msg.get("model") or
                            (cur["model"] if cur else None),
                            "age_s": round(age, 1),
                            "state": "running" if age <= LIVE_WINDOW_S
                            else "recent",
                            "activity": _activity(e)}
    return sorted(out.values(), key=lambda r: r["age_s"])


def open_windows(run=subprocess.run):
    """Per-directory count of open Claude Code processes (read-only ps +
    lsof). Covers "open but idle" — a window that isn't conversing writes
    no history, so file mtimes cannot see it. A process cannot be matched
    to a specific session file: the count is per cwd, honestly coarse.
    Any failure degrades to an empty list — never an error, never a guess."""
    try:
        ps = run(["ps", "-axo", "pid=,comm="], capture_output=True,
                 text=True, timeout=3).stdout
        pids = [parts[0] for line in ps.splitlines()
                if len(parts := line.split(None, 1)) == 2
                and parts[1].rsplit("/", 1)[-1] == "claude"]
        if not pids:
            return []
        lo = run(["lsof", "-a", "-d", "cwd", "-p", ",".join(pids), "-Fn"],
                 capture_output=True, text=True, timeout=3).stdout
        counts = {}
        for line in lo.splitlines():
            if line.startswith("n"):
                counts[line[1:]] = counts.get(line[1:], 0) + 1
        return [{"cwd": c, "count": n} for c, n in sorted(counts.items())]
    except Exception:  # ponytail: any probe failure = feature absent
        return []
