"""Liveness contract: mtime window, tail parse, subagent roll-up."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from ccwhere import live


def _write(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")


class TestLive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_session_listed_with_tail(self):
        f = self.root / "-proj" / "abc.jsonl"
        _write(f, [
            {"type": "user", "message": {"content": "go"}},
            {"type": "assistant", "message": {
                "model": "claude-fable-5",
                "content": [{"type": "tool_use", "name": "Bash",
                             "input": {"command": "ls"}}]}},
            "not-a-dict-line-should-be-skipped",
        ])
        rows = live.live_sessions(projects_root=self.root)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["session"], "abc")
        self.assertEqual(r["project"], "-proj")
        self.assertEqual(r["model"], "claude-fable-5")
        self.assertEqual(r["activity"], "running Bash")
        self.assertLess(r["age_s"], 60)

    def test_bands_and_stale_cutoff(self):
        fresh = self.root / "-proj" / "fresh.jsonl"
        _write(fresh, [{"type": "user", "message": {"content": "x"}}])
        recent = self.root / "-proj" / "recent.jsonl"
        _write(recent, [{"type": "user", "message": {"content": "x"}}])
        t = time.time() - 480          # 8 min: recently active
        os.utime(recent, (t, t))
        gone = self.root / "-proj" / "gone.jsonl"
        _write(gone, [{"type": "user", "message": {"content": "x"}}])
        t = time.time() - 1200         # 20 min: history, not live
        os.utime(gone, (t, t))
        rows = {r["session"]: r for r in
                live.live_sessions(projects_root=self.root)}
        self.assertEqual(rows["fresh"]["state"], "running")
        self.assertEqual(rows["recent"]["state"], "recent")
        self.assertNotIn("gone", rows)

    def test_open_windows_counts_per_cwd(self):
        class R:
            def __init__(self, stdout):
                self.stdout = stdout

        def fake_run(cmd, **kw):
            if cmd[0] == "ps":
                return R("1 /ext/native-binary/claude\n"
                         "2 /ext/native-binary/claude\n"
                         "3 /Applications/Claude.app/Contents/MacOS/Claude\n"
                         "4 /usr/bin/grep\n")
            return R("p1\nn/Users/me/my-os\np2\nn/Users/me/my-os\n")
        wins = live.open_windows(run=fake_run)
        self.assertEqual(wins, [{"cwd": "/Users/me/my-os", "count": 2}])

    def test_open_windows_degrades_to_empty(self):
        def broken_run(cmd, **kw):
            raise OSError("no ps here")
        self.assertEqual(live.open_windows(run=broken_run), [])

    def test_subagent_rolls_up_to_parent(self):
        sub = self.root / "-proj" / "parent1" / "subagents" / "agent-z.jsonl"
        _write(sub, [{"type": "assistant", "message": {
            "model": "claude-haiku-4-5",
            "content": [{"type": "text", "text": "hi"}]}}])
        rows = live.live_sessions(projects_root=self.root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session"], "parent1")
        self.assertEqual(rows[0]["activity"], "assistant responding")

    def test_missing_root_is_empty(self):
        self.assertEqual(
            live.live_sessions(projects_root=self.root / "nope"), [])


if __name__ == "__main__":
    unittest.main()
