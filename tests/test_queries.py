"""Query contract: lenses, flags, local-time bucketing, deltas, cache rate.
Fixture is TZ-agnostic: timestamps built from local datetimes."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ccwhere import db, queries


def L(y, m, d, h=12, mi=0):
    """Local wall-clock time -> stored UTC ISO string."""
    return datetime(y, m, d, h, mi).astimezone().astimezone(timezone.utc).isoformat()


class TestQueries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self.tmp.name) / "q.db")
        c = self.conn

        def sess(sid, proj, parent=None, cwd=None):
            c.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?)",
                      (sid, proj, "", parent, cwd, None, None))

        def msg(sid, ln, ts, out=0, inp=0, cr=0, cc=0):
            c.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (sid, ln, f"{sid}-{ln}", ts, "assistant", "m",
                       inp, out, cr, cc))

        def tool(tid, sid, ln, ts, consumer):
            c.execute("INSERT INTO tool_calls VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (tid, sid, ln, ts, consumer, "skill", consumer,
                       None, None, 0))

        sess("s1", "projA"); sess("s2", "projB"); sess("s3", "projA")
        # s1, day1: 900 + 100; consumer X invoked on the 100-token message
        msg("s1", 1, L(2026, 7, 1, 10), out=900)
        msg("s1", 2, L(2026, 7, 1, 11), out=100)
        tool("t1", "s1", 2, L(2026, 7, 1, 11), "X")
        # s2 spans local midnight: 300 on day1 at 23:30, 200 on day2 at 00:30
        msg("s2", 1, L(2026, 7, 1, 23, 30), out=300)
        tool("t2", "s2", 1, L(2026, 7, 1, 23, 30), "X")
        msg("s2", 2, L(2026, 7, 2, 0, 30), out=200)
        # s3, day2: cache-heavy message; consumer W appears only here (N=1)
        msg("s3", 1, L(2026, 7, 2, 9), inp=100, cr=700, cc=200)
        tool("t3", "s3", 1, L(2026, 7, 2, 9), "W")
        # 10 filler consumers with big direct tokens in s1 (day1):
        # X stays #1 on the Session lens but drops outside top-10 on Message.
        for i in range(10):
            ln = 10 + i
            msg("s1", ln, L(2026, 7, 1, 12), out=500 + i)
            tool(f"tf{i}", "s1", ln, L(2026, 7, 1, 12), f"c{i}")
        # a built-in tool call: excluded from the league by default
        msg("s1", 30, L(2026, 7, 1, 13), out=50)
        c.execute("INSERT INTO tool_calls VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("tb1", "s1", 30, L(2026, 7, 1, 13), "Bash", "builtin",
                   "Bash", None, None, 0))
        # a CLI program call (installed → actionable): in the default league
        msg("s1", 31, L(2026, 7, 1, 13), out=60)
        c.execute("INSERT INTO tool_calls VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("tc1", "s1", 31, L(2026, 7, 1, 13), "Bash", "cli",
                   "vercel", None, None, 0))
        # a shell utility call: excluded by default like built-ins
        msg("s1", 32, L(2026, 7, 1, 13), out=70)
        c.execute("INSERT INTO tool_calls VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("ts1", "s1", 32, L(2026, 7, 1, 13), "Bash", "shell",
                   "grep", None, None, 0))
        c.commit()
        self.f = {"from": "2026-07-01", "to": "2026-07-02", "projects": None}

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_session_lens_ranks_X_first(self):
        rows = queries.league(self.conn, self.f)
        self.assertEqual(rows[0]["consumer"], "X")  # s1+s2 totals beat s1-only
        self.assertEqual(rows[0]["sessions"], 2)

    def test_message_lens_exact_linkage(self):
        rows = {r["consumer"]: r for r in queries.league(self.conn, self.f)}
        self.assertEqual(rows["X"]["message_tokens"], 400)   # 100 + 300, exact
        self.assertEqual(rows["c0"]["message_tokens"], 500)

    def test_flags(self):
        rows = {r["consumer"]: r for r in queries.league(self.conn, self.f)}
        self.assertEqual(rows["X"]["flag"], "disagree")  # top-5 A, rank 11+ B
        self.assertEqual(rows["W"]["flag"], "n1")
        self.assertEqual(len(rows["X"]["spark"]), 14)

    def test_local_day_split(self):
        d = {r["date"]: r for r in queries.daily(self.conn, self.f)}
        day1 = d["2026-07-01"]
        day2 = d["2026-07-02"]
        total1 = day1["input"] + day1["output"] + day1["cache_read"] + day1["cache_create"]
        total2 = day2["input"] + day2["output"] + day2["cache_read"] + day2["cache_create"]
        self.assertEqual(total1,
                         900 + 100 + 300 + 50 + 60 + 70 + sum(500 + i for i in range(10)))
        self.assertEqual(total2, 200 + 1000)  # 00:30 message lands on day2

    def test_strip_prev_window_delta(self):
        s = queries.strip(self.conn, {"from": "2026-07-02", "to": "2026-07-02",
                                      "projects": None})
        self.assertEqual(s["tokens"], 1200)
        self.assertEqual(s["tokens_prev"],
                         900 + 100 + 300 + 50 + 60 + 70 + sum(500 + i for i in range(10)))

    def test_cache_rate(self):
        s = queries.strip(self.conn, self.f)
        self.assertEqual(s["cache_rate_pct"], 70.0)  # 700/(100+700+200)

    def test_project_filter(self):
        f = dict(self.f, projects=["projB"])
        rows = queries.league(self.conn, f)
        self.assertEqual([r["consumer"] for r in rows], ["X"])
        self.assertEqual(rows[0]["session_tokens"], 500)  # s2 only

    def test_builtins_excluded_by_default(self):
        consumers = [r["consumer"] for r in queries.league(self.conn, self.f)]
        self.assertNotIn("Bash", consumers)
        with_builtins = [r["consumer"] for r in queries.league(
            self.conn, dict(self.f, types=["skill", "mcp", "builtin"]))]
        self.assertIn("Bash", with_builtins)

    def test_demoted_cli_treated_as_shell(self):
        f = dict(self.f, demoted={"vercel"})
        rows = {r["consumer"]: r for r in queries.league(self.conn, f)}
        self.assertNotIn("vercel", rows)  # demoted = out of the default view
        self.assertEqual(rows["X"]["message_tokens"], 400)  # others untouched
        with_shell = {r["consumer"]: r for r in queries.league(
            self.conn, dict(f, types=["skill", "mcp", "cli", "shell"]))}
        self.assertEqual(with_shell["vercel"]["type"], "shell")  # remapped
        self.assertEqual(with_shell["vercel"]["message_tokens"], 60)

    def test_cli_in_default_shell_on_demand(self):
        rows = {r["consumer"]: r for r in queries.league(self.conn, self.f)}
        self.assertIn("vercel", rows)  # installed = actionable = default
        self.assertEqual(rows["vercel"]["type"], "cli")
        self.assertEqual(rows["vercel"]["message_tokens"], 60)  # exact linkage
        self.assertNotIn("grep", rows)  # shell utility waits for its toggle
        with_shell = {r["consumer"]: r for r in queries.league(
            self.conn, dict(self.f, types=["skill", "mcp", "cli", "shell"]))}
        self.assertIn("grep", with_shell)
        # existing rows unchanged by the toggle
        self.assertEqual(with_shell["X"]["message_tokens"], 400)

    def test_performance_grain_orphans_errors(self):
        c = self.conn
        ins = ("INSERT INTO tool_calls VALUES (?,?,?,?,?,?,?,?,?,?)")
        # mcp: two tools on one server -> two rows (tool grain)
        for i in range(10):
            c.execute(ins, (f"pn{i}", "s1", 100 + i, L(2026, 7, 1, 14),
                            "mcp__pw__navigate", "mcp", "pw", "navigate",
                            (i + 1) * 100, 0))
        # 2 orphans: count as calls, never enter percentiles
        c.execute(ins, ("po1", "s1", 120, L(2026, 7, 1, 14),
                        "mcp__pw__navigate", "mcp", "pw", "navigate",
                        None, None))
        c.execute(ins, ("po2", "s1", 121, L(2026, 7, 1, 14),
                        "mcp__pw__navigate", "mcp", "pw", "navigate",
                        None, None))
        c.execute(ins, ("pc1", "s1", 122, L(2026, 7, 1, 14),
                        "mcp__pw__click", "mcp", "pw", "click", 50, 1))
        # command rows carry no latency: excluded entirely
        c.execute(ins, ("pcmd", "s1", 123, L(2026, 7, 1, 14),
                        "command", "command", "write-prd", None, None, None))
        c.commit()
        rows = {r["consumer"]: r for r in queries.performance(self.conn, self.f)}
        nav = rows["pw · navigate"]
        self.assertEqual(nav["type"], "mcp")
        self.assertEqual(nav["calls"], 12)      # orphans counted
        self.assertEqual(nav["n_paired"], 10)   # ...but not measured
        self.assertEqual(nav["p50"], 550)       # median of 100..1000
        self.assertEqual(nav["p95"], 1000)      # nearest-rank on n=10
        self.assertEqual(nav["max"], 1000)
        self.assertEqual(nav["err_rate"], 0)
        click = rows["pw · click"]
        self.assertEqual(click["err_rate"], 1.0)
        self.assertNotIn("write-prd", rows)
        # skill row from base fixture has no durations: no fabricated numbers
        self.assertIsNone(rows["X"]["p50"])

    def test_ledger_medians_parent_only_and_floor(self):
        c = self.conn
        # give projA a third parent session so it can calibrate the floor
        c.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?)",
                  ("s4", "projA", "", None, "/tmp/projA", None, None))
        c.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("s4", 1, "s4-1", L(2026, 7, 2, 10), "assistant", "m",
                   200, 0, 300, 0))
        # a subagent session with a huge first call: must not affect medians
        c.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?)",
                  ("s1/agent-z", "projA", "", "s1", None, None, None))
        c.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("s1/agent-z", 1, "z-1", L(2026, 7, 2, 11), "assistant", "m",
                   999999, 0, 0, 0))
        c.commit()
        led = queries.ledger_medians(self.conn)
        by = {r["project"]: r for r in led["projects"]}
        # projA first calls: s1=0, s3=1000, s4=500 -> median 500, n=3
        self.assertEqual(by["projA"]["median"], 500)
        self.assertEqual(by["projA"]["n"], 3)
        self.assertEqual(by["projA"]["cwd"], "/tmp/projA")
        self.assertEqual(by["projB"]["n"], 1)  # low sample, still listed
        # only projA (n>=3) may calibrate the floor
        self.assertEqual(led["floor"], 500)

    def test_events_drill(self):
        # the hour of s3's message, in local time
        date, hour = self.conn.execute(
            "SELECT date(datetime(ts,'localtime')),"
            " CAST(strftime('%H', datetime(ts,'localtime')) AS INT)"
            " FROM tool_calls WHERE tool_use_id='t3'").fetchone()
        ev = queries.events(self.conn, self.f, date, hour)
        w = [e for e in ev if e["consumer"] == "W"]
        self.assertEqual(len(w), 1)
        self.assertEqual(w[0]["tokens"], 1000)
        self.assertEqual(w[0]["project"], "projA")


if __name__ == "__main__":
    unittest.main()
