"""Localhost-only HTTP server: static ui/ + JSON API for the shell."""
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import db, ingest, live, queries, scan

UI_ROOT = (Path(__file__).parent / "ui").resolve()
CANARY_THRESHOLD_PCT = 1.0
_sync_lock = threading.Lock()  # ponytail: global lock, single operator

MIME = {".html": "text/html", ".js": "application/javascript",
        ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png"}


def _health(db_path):
    conn = db.connect(db_path)
    try:
        run = conn.execute(
            "SELECT started_at, elapsed_ms, total_events, unknown_types "
            "FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        age = drift = None
        if run:
            started = datetime.fromisoformat(run[0])
            age = (datetime.now(timezone.utc) - started).total_seconds()
            unknown = sum(json.loads(run[3] or "{}").values())
            drift = round(unknown / run[2] * 100, 2) if run[2] else 0.0
        rows = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("messages", "tool_calls", "sessions")}
        return {"last_sync_age_s": age, "drift_pct": drift,
                "canary_threshold_pct": CANARY_THRESHOLD_PCT, "rows": rows}
    finally:
        conn.close()


def _summary(db_path):
    conn = db.connect(db_path)
    try:
        one = lambda sql: conn.execute(sql).fetchone()[0]
        return {
            "sessions": one("SELECT COUNT(*) FROM sessions"),
            "projects": one("SELECT COUNT(DISTINCT project) FROM sessions"),
            "messages": one("SELECT COUNT(*) FROM messages"),
            "first_ts": one("SELECT MIN(ts) FROM messages"),
            "last_ts": one("SELECT MAX(ts) FROM messages"),
        }
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the terminal quiet
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")  # data is never stale
        self.end_headers()
        self.wfile.write(body)

    def _filters(self, q):
        return {"from": q.get("from", [None])[0],
                "to": q.get("to", [None])[0],
                "projects": q["projects"][0].split(",")
                if q.get("projects", [""])[0] else None,
                "types": q["types"][0].split(",")
                if q.get("types", [""])[0] else None,
                "fresh": q.get("fresh", ["0"])[0] == "1"}

    def do_GET(self):
        u = urlparse(self.path)
        path, q = u.path, parse_qs(u.query)
        if path == "/api/health":
            return self._json(_health(self.server.db_path))
        if path == "/api/summary":
            return self._json(_summary(self.server.db_path))
        if path == "/api/ledger":
            conn = db.connect(self.server.db_path)
            try:
                led = queries.ledger_medians(conn)
                usage = queries.skill_usage(conn)
            finally:
                conn.close()

            def attach_usage(items):
                for it in items:
                    skills = it.get("skills")
                    if not skills:
                        continue
                    for sk in skills:
                        sk["usage"] = queries.match_skill_usage(
                            usage, {sk["name"], sk.get("dir")}, sk["pkg"])
                    # prune-priority order: never-used first, biggest first
                    skills.sort(key=lambda s: (s["usage"]["uses"] > 0,
                                               s["usage"]["uses"],
                                               -s["tokens"]))
                return items

            floor = led["floor"]
            projects = []
            for p in led["projects"]:
                items = attach_usage(scan.project_items(p["cwd"], p["project"]))
                itemized = sum(i["tokens"] or 0 for i in items)
                projects.append({**p, "items": items, "itemized": itemized,
                                 "floor": min(floor, p["median"]),
                                 "unattributed": max(
                                     p["median"] - floor - itemized, 0)})
            return self._json({"floor": floor,
                               "floor_items": attach_usage(scan.floor_items()),
                               "projects": projects})
        if path == "/api/live":
            return self._json({"sessions": live.live_sessions(
                projects_root=self.server.projects_root),
                "open": live.open_windows()})
        if path == "/api/performance":
            f = self._filters(q)
            f["demoted"] = db.load_overrides(self.server.db_path)
            conn = db.connect(self.server.db_path)
            try:
                return self._json({
                    "rows": queries.performance(conn, f),
                    "projects": queries.project_list(conn)})
            finally:
                conn.close()
        if path == "/api/consumption":
            f = self._filters(q)
            f["demoted"] = db.load_overrides(self.server.db_path)
            prices = db.load_prices(self.server.db_path)
            conn = db.connect(self.server.db_path)
            try:
                mrows = queries.models(conn, f)
                cost = queries.priced(mrows, prices)
                pf = queries.prev_window(f)
                cost["usd_prev"] = queries.priced(
                    queries.models(conn, pf), prices)["usd"] if pf else None
                return self._json({
                    "strip": queries.strip(conn, f),
                    "daily": queries.daily(conn, f),
                    "league": queries.league(conn, f),
                    "models": mrows,
                    "cost": cost,
                    "projects": queries.project_list(conn),
                    "demoted": sorted(f["demoted"])})
            finally:
                conn.close()
        if path == "/api/consumption/models":
            f = self._filters(q)
            prices = db.load_prices(self.server.db_path)
            conn = db.connect(self.server.db_path)
            try:
                rows = queries.models(
                    conn, f, date=q.get("date", [None])[0],
                    hour=int(q["hour"][0]) if q.get("hour") else None)
                return self._json({"models": rows,
                                   "cost": queries.priced(rows, prices)})
            finally:
                conn.close()
        if path == "/api/consumption/hours":
            f = self._filters(q)
            conn = db.connect(self.server.db_path)
            try:
                return self._json(queries.hours(conn, f, q["date"][0]))
            finally:
                conn.close()
        if path == "/api/consumption/events":
            f = self._filters(q)
            f["demoted"] = db.load_overrides(self.server.db_path)
            conn = db.connect(self.server.db_path)
            try:
                # drill floor shows all evidence, built-ins included
                return self._json(queries.events(
                    conn, dict(f, types=None), q["date"][0], int(q["hour"][0])))
            finally:
                conn.close()
        if path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        self._static(path)

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/sync":
            with _sync_lock:
                s = ingest.sync(projects_root=self.server.projects_root,
                                db_path=self.server.db_path)
            return self._json(s)
        if path == "/api/overrides":
            try:
                body = json.loads(self.rfile.read(
                    int(self.headers.get("Content-Length", 0))))
                consumer = str(body["consumer"])
                demote = bool(body["demoted"])
            except (ValueError, KeyError, TypeError):
                return self._json({"error": "bad request"}, 400)
            demoted = db.load_overrides(self.server.db_path)
            (demoted.add if demote else demoted.discard)(consumer)
            db.save_overrides(demoted, self.server.db_path)
            return self._json({"demoted": sorted(demoted)})
        self._json({"error": "not found"}, 404)

    def _static(self, path):
        rel = path.lstrip("/") or "index.html"
        target = (UI_ROOT / rel).resolve()
        if not str(target).startswith(str(UI_ROOT)) or not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",
                         MIME.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        # localhost: everything is instant; stale UI after an upgrade is worse
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def make_server(port: int, db_path=None, projects_root=None) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.db_path = db_path
    srv.projects_root = projects_root
    return srv
