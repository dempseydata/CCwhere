"""Scan contract: itemization from a project cwd, floor estimate from
installed_plugins.json, silence on missing paths."""
import json
import tempfile
import unittest
from pathlib import Path

from ccwhere import scan


class TestScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_project_items(self):
        cwd = self.root / "proj"
        (cwd / ".claude" / "skills" / "myskill").mkdir(parents=True)
        (cwd / "CLAUDE.md").write_text("x" * 4000)          # ~1000 tok
        (cwd / "AGENTS.md").write_text("y" * 2000)          # ~500 tok
        (cwd / ".claude" / "skills" / "myskill" / "SKILL.md").write_text(
            "---\nname: myskill\ndescription: does a thing, quite well\n---\n")
        home = self.root / "claude-home"
        mem = home / "projects" / "-proj" / "memory"
        mem.mkdir(parents=True)
        (mem / "MEMORY.md").write_text("m" * 400)           # ~100 tok
        items = {i["name"]: i for i in scan.project_items(
            str(cwd), "-proj", claude_home=home)}
        self.assertEqual(items["CLAUDE.md"]["tokens"], 1000)
        self.assertEqual(items["AGENTS.md"]["tokens"], 500)
        self.assertEqual(items["memory/MEMORY.md"]["tokens"], 100)
        self.assertIn(".claude/skills+commands (1)", items)
        self.assertTrue(all(i["tag"] == "prunable" for i in items.values()))

    def test_missing_cwd_yields_empty(self):
        self.assertEqual(
            scan.project_items("/nonexistent/path", "-x",
                               claude_home=self.root / "nohome"), [])

    def test_floor_items_from_installed_plugins(self):
        home = self.root / "claude-home"
        plug = home / "plugins" / "cache" / "mkt" / "tool" / "1.0.0"
        sk = plug / "skills" / "s1"
        sk.mkdir(parents=True)
        (sk / "SKILL.md").write_text(
            "---\nname: s1\ndescription: " + "d" * 360 + "\n---\n")
        (home / "plugins").mkdir(exist_ok=True)
        (home / "plugins" / "installed_plugins.json").write_text(json.dumps(
            {"version": 2, "plugins": {"tool@mkt": [
                {"installPath": str(plug), "version": "1.0.0"}]}}))
        items = scan.floor_items(claude_home=home)
        self.assertEqual(items[0]["name"], "plugin skills & commands (1)")
        self.assertEqual(items[0]["tokens"], 100)  # (360+40)/4
        self.assertEqual(items[-1]["tag"], "fixed")
        self.assertIsNone(items[-1]["tokens"])  # no invented numbers

    def test_floor_items_include_user_level_files(self):
        home = self.root / "claude-home"
        sk = home / "skills" / "mine"
        sk.mkdir(parents=True)
        (home / "CLAUDE.md").write_text("u" * 800)          # ~200 tok
        (sk / "SKILL.md").write_text(
            "---\nname: mine\ndescription: " + "d" * 360 + "\n---\n")
        items = {i["name"]: i for i in scan.floor_items(claude_home=home)}
        self.assertEqual(items["~/.claude/CLAUDE.md"]["tokens"], 200)
        user = items["~/.claude/skills+commands (1)"]
        self.assertEqual(user["tokens"], 100)
        self.assertEqual(user["skills"][0]["pkg"], "(user)")

    def test_floor_items_survive_missing_registry(self):
        items = scan.floor_items(claude_home=self.root / "empty")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["tag"], "fixed")


if __name__ == "__main__":
    unittest.main()
