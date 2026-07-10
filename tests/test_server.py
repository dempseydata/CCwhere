"""Server contract test: API round-trips, traversal guard, localhost bind,
port-conflict fail-fast. Reuses the ingest fixture."""
import http.client
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen, Request

from ccwhere import ingest, server
from ccwhere.__main__ import main
from tests.test_ingest import build_fixture


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / "projects"
        cls.db_path = Path(cls.tmp.name) / "test.db"
        build_fixture(cls.root)
        ingest.sync(projects_root=cls.root, db_path=cls.db_path)
        cls.srv = server.make_server(0, db_path=cls.db_path,
                                     projects_root=cls.root)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def get(self, path):
        with urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.status, r.read()

    def get_json(self, path):
        status, body = self.get(path)
        return status, json.loads(body)

    def test_binds_localhost_only(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")

    def test_health(self):
        status, h = self.get_json("/api/health")
        self.assertEqual(status, 200)
        self.assertLess(h["drift_pct"], 100)
        self.assertEqual(h["canary_threshold_pct"], 1.0)
        self.assertIn("last_sync_age_s", h)
        self.assertGreater(h["rows"]["messages"], 0)

    def test_summary(self):
        status, s = self.get_json("/api/summary")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(s["sessions"], 2)  # main + subagent
        self.assertGreaterEqual(s["projects"], 1)

    def test_sync_roundtrip(self):
        req = Request(f"http://127.0.0.1:{self.port}/api/sync", method="POST")
        with urlopen(req) as r:
            body = json.loads(r.read())
        self.assertEqual(body["files_parsed"], 0)  # nothing changed
        _, h = self.get_json("/api/health")
        self.assertLess(h["last_sync_age_s"], 5)

    def test_index_served(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"ccwhere", body)

    def test_unknown_api_is_json_404(self):
        try:
            self.get("/api/nope")
            self.fail("expected 404")
        except Exception as e:
            self.assertEqual(e.code, 404)
            self.assertIn("application/json", e.headers.get("Content-Type", ""))

    def test_traversal_guard(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.request("GET", "/../ccwhere/db.py")  # raw path, no client normalization
        r = c.getresponse()
        self.assertIn(r.status, (403, 404))
        c.close()

    def test_consumption_payload(self):
        status, c = self.get_json("/api/consumption")
        self.assertEqual(status, 200)
        self.assertGreater(len(c["league"]), 0)
        self.assertIn("plugin_playwright_playwright",
                      [r["consumer"] for r in c["league"]])
        self.assertIn("strip", c)
        self.assertIn("projects", c)

    def test_consumption_drill(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        date, hour = conn.execute(
            "SELECT date(datetime(ts,'localtime')),"
            " CAST(strftime('%H', datetime(ts,'localtime')) AS INT)"
            " FROM tool_calls LIMIT 1").fetchone()
        conn.close()
        status, hrs = self.get_json(f"/api/consumption/hours?date={date}")
        self.assertEqual(status, 200)
        self.assertGreater(len(hrs), 0)
        status, ev = self.get_json(
            f"/api/consumption/events?date={date}&hour={hour}")
        self.assertEqual(status, 200)
        self.assertGreater(len(ev), 0)
        self.assertIn("tokens", ev[0])

    def test_live_payload(self):
        # fixture files were written moments ago: they are live by definition
        status, l = self.get_json("/api/live")
        self.assertEqual(status, 200)
        sessions = {r["session"]: r for r in l["sessions"]}
        self.assertIn("11111111-1111-1111-1111-111111111111", sessions)
        r = sessions["11111111-1111-1111-1111-111111111111"]
        self.assertLess(r["age_s"], 300)
        self.assertIn("activity", r)

    def test_performance_payload(self):
        status, p = self.get_json("/api/performance")
        self.assertEqual(status, 200)
        rows = {r["consumer"]: r for r in p["rows"]}
        # fixture: t_mcp paired at 4200ms; t_bash (cli 'ls') is an orphan
        nav = rows["plugin_playwright_playwright · browser_navigate"]
        self.assertEqual(nav["p50"], 4200)
        self.assertEqual(nav["calls"], 1)
        ls = rows["ls"]
        self.assertEqual(ls["calls"], 1)
        self.assertIsNone(ls["p50"])  # orphan: no fabricated latency
        # filtered round-trip
        status, p2 = self.get_json("/api/performance?projects=nope")
        self.assertEqual(p2["rows"], [])

    def test_ledger_payload(self):
        status, led = self.get_json("/api/ledger")
        self.assertEqual(status, 200)
        tree = led["tree"]
        self.assertEqual(tree[0]["label"], "user level (~/.claude)")
        self.assertEqual(tree[0]["items"][-1]["tag"], "fixed")  # harness line
        # accumulated grows monotonically down each branch (dormant nodes
        # carry no numbers and are exempt)
        for nd in tree[1:]:
            if nd.get("dormant"):
                self.assertIsNone(nd["accumulated"])
                continue
            self.assertGreaterEqual(nd["accumulated"], nd["additional"])
            for key in ("label", "depth", "items"):
                self.assertIn(key, nd)
        # session nodes carry median + clamped unattributed
        withmed = [nd for nd in tree if nd.get("median") is not None]
        self.assertGreaterEqual(len(withmed), 1)
        self.assertGreaterEqual(withmed[0]["unattributed"], 0)

    def test_overrides_demote_roundtrip(self):
        def post(body):
            req = Request(f"http://127.0.0.1:{self.port}/api/overrides",
                          data=json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"})
            with urlopen(req) as r:
                return r.status, json.loads(r.read())

        _, c = self.get_json("/api/consumption")
        self.assertIn("vercel", [r["consumer"] for r in c["league"]])
        status, o = post({"consumer": "vercel", "demoted": True})
        self.assertEqual(status, 200)
        self.assertEqual(o["demoted"], ["vercel"])
        _, c = self.get_json("/api/consumption")
        self.assertNotIn("vercel", [r["consumer"] for r in c["league"]])
        self.assertEqual(c["demoted"], ["vercel"])
        # visible under the shell toggle, remapped type
        _, c = self.get_json("/api/consumption?types=skill,mcp,cli,shell")
        row = {r["consumer"]: r for r in c["league"]}["vercel"]
        self.assertEqual(row["type"], "shell")
        # restore reverses everything
        post({"consumer": "vercel", "demoted": False})
        _, c = self.get_json("/api/consumption")
        self.assertIn("vercel", [r["consumer"] for r in c["league"]])
        self.assertEqual(c["demoted"], [])

    def test_overrides_bad_request(self):
        req = Request(f"http://127.0.0.1:{self.port}/api/overrides",
                      data=b"not json", headers={})
        try:
            with urlopen(req) as r:
                status = r.status
        except Exception as e:  # urllib raises on 4xx
            status = e.code
        self.assertEqual(status, 400)

    def test_port_conflict_fails_fast(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        busy_port = s.getsockname()[1]
        rc = main(["--port", str(busy_port), "--no-browser"])
        self.assertNotEqual(rc, 0)
        s.close()


if __name__ == "__main__":
    unittest.main()
