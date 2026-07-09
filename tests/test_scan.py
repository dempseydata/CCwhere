"""Scan contract: the context tree — eager stubs vs on-use catalog,
additional/accumulated math, single-branch accumulation."""
import json
import tempfile
import unittest
from pathlib import Path

from ccwhere import scan


class TestScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "claude-home"

    def tearDown(self):
        self.tmp.cleanup()

    def _skill_at(self, d, name):
        sk = d / ".claude" / "skills" / name
        sk.mkdir(parents=True)
        (sk / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: " + "d" * 360 + "\n---\n")

    def _registry(self, plugins):
        entries = {}
        for key in plugins:
            p = self.home / "plugins" / "cache" / key.replace("@", "-") / "1"
            sk = p / "skills" / "s"
            sk.mkdir(parents=True)
            (sk / "SKILL.md").write_text(
                "---\nname: s\ndescription: " + "d" * 360 + "\n---\n")
            entries[key] = [{"installPath": str(p), "version": "1"}]
        (self.home / "plugins").mkdir(exist_ok=True)
        (self.home / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": entries}))

    def _tree(self, projects):
        return scan.context_tree(projects, claude_home=self.home,
                                 stop_at=self.root)

    def test_tree_additional_and_accumulated(self):
        (self.home).mkdir(parents=True, exist_ok=True)
        (self.home / "CLAUDE.md").write_text("u" * 400)     # 100 tok
        self._registry(["u@m", "p@m"])
        (self.home / "settings.json").write_text(json.dumps(
            {"enabledPlugins": {"u@m": True}}))
        proj = self.root / "work" / "projA"   # 'work' has no content: skipped
        proj.mkdir(parents=True)
        (proj / "CLAUDE.md").write_text("x" * 4000)         # 1000 tok
        self._skill_at(proj, "s1")                          # catalog 100
        (proj / ".claude" / "settings.json").write_text(json.dumps(
            {"enabledPlugins": {"p@m": True}}))
        sub = proj / "slice"
        sub.mkdir()
        (sub / "CLAUDE.md").write_text("y" * 2000)          # 500 tok

        nodes = self._tree([
            {"project": "-a", "cwd": str(proj), "median": 30_000, "n": 5},
            {"project": "-b", "cwd": str(sub), "median": 31_000, "n": 1},
        ])
        user, a, b = nodes[0], nodes[1], nodes[2]
        # user: CLAUDE.md 100 + 1 user-plugin entry stub
        self.assertEqual(user["additional"], 100 + scan.EAGER_STUB_TOK)
        self.assertEqual(user["accumulated"], user["additional"])
        # projA: CLAUDE.md 1000 + skill stub + project-plugin stub
        self.assertEqual(a["additional"], 1000 + 2 * scan.EAGER_STUB_TOK)
        self.assertEqual(a["accumulated"],
                         user["accumulated"] + a["additional"])
        self.assertEqual(a["median"], 30_000)
        self.assertEqual(a["depth"], 1)   # 'work' skipped, parent is user
        # slice: only its CLAUDE.md; accumulates along the branch
        self.assertEqual(b["additional"], 500)
        self.assertEqual(b["accumulated"], a["accumulated"] + 500)
        self.assertEqual(b["depth"], 2)

    def test_stub_vs_catalog_split(self):
        self.home.mkdir(parents=True)
        proj = self.root / "p"
        self._skill_at(proj, "big")
        nodes = self._tree([{"project": "-p", "cwd": str(proj),
                             "median": 1, "n": 1}])
        item = next(i for i in nodes[1]["items"] if i.get("skills"))
        self.assertEqual(item["tokens"], scan.EAGER_STUB_TOK)  # eager stub
        self.assertEqual(item["catalog"], 100)                 # on-use size
        self.assertEqual(item["skills"][0]["name"], "big")

    def test_disabled_plugin_appears_nowhere(self):
        self.home.mkdir(parents=True, exist_ok=True)
        self._registry(["off@m"])
        (self.home / "settings.json").write_text(json.dumps(
            {"enabledPlugins": {"off@m": False}}))
        proj = self.root / "p"
        proj.mkdir()
        (proj / "CLAUDE.md").write_text("x" * 40)
        nodes = self._tree([{"project": "-p", "cwd": str(proj),
                             "median": 1, "n": 1}])
        names = [i["name"] for n in nodes for i in n["items"]]
        self.assertFalse(any("plugin" in n and "user" in n for n in names))

    def test_no_enablement_key_means_installed_loads(self):
        self.home.mkdir(parents=True, exist_ok=True)
        self._registry(["a@m"])  # no settings.json at all
        nodes = self._tree([])
        names = [i["name"] for i in nodes[0]["items"]]
        self.assertIn("user plugins (1)", names)

    def test_missing_paths_yield_quiet_tree(self):
        self.home.mkdir(parents=True, exist_ok=True)
        nodes = self._tree([{"project": "-x", "cwd": "/nonexistent/path",
                             "median": 1, "n": 1}])
        self.assertEqual(nodes[0]["label"], "user level (~/.claude)")
        # nonexistent cwd still gets a node, with nothing in it
        self.assertEqual(nodes[1]["additional"], 0)


if __name__ == "__main__":
    unittest.main()
