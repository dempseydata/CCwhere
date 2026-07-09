"""Parser/sync contract test. Fixture mimics real ~/.claude/projects shapes
verified on this machine during definition (2026-07-07)."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ccwhere import ingest


def _line(**kw):
    return json.dumps(kw)


def build_fixture(root: Path):
    proj = root / "-Users-me-code-demo"
    proj.mkdir(parents=True)
    f = proj / "11111111-1111-1111-1111-111111111111.jsonl"
    lines = [
        _line(type="user", uuid="u1", timestamp="2026-07-07T14:00:00.000Z",
              cwd="/Users/me/code/demo",
              message={"role": "user", "content": "do the thing"}),
        # assistant with usage + Skill + MCP tool_use
        _line(type="assistant", uuid="a1", timestamp="2026-07-07T14:00:05.000Z",
              message={"role": "assistant", "model": "claude-fable-5",
                       "usage": {"input_tokens": 12, "output_tokens": 340,
                                 "cache_read_input_tokens": 39810,
                                 "cache_creation_input_tokens": 1200,
                                 "speed": "fast", "brand_new_field": 1},
                       "content": [
                           {"type": "tool_use", "id": "t_skill",
                            "name": "Skill",
                            "input": {"skill": "pm-execution:write-prd"}},
                           {"type": "tool_use", "id": "t_mcp",
                            "name": "mcp__plugin_playwright_playwright__browser_navigate",
                            "input": {"url": "http://x"}},
                       ]}),
        # tool_result pairing t_mcp 4.2s after its tool_use
        _line(type="user", uuid="u2", timestamp="2026-07-07T14:00:09.200Z",
              message={"role": "user", "content": [
                  {"type": "tool_result", "tool_use_id": "t_mcp",
                   "is_error": False, "content": "ok"}]}),
        # Bash tool_uses: extractable command (cli), no command (builtin
        # fallback); t_bash never gets a result (orphan)
        _line(type="assistant", uuid="a2", timestamp="2026-07-07T14:01:00.000Z",
              message={"role": "assistant", "model": "claude-fable-5",
                       "usage": {"input_tokens": 5, "output_tokens": 20},
                       "content": [{"type": "tool_use", "id": "t_bash",
                                    "name": "Bash", "input": {"command": "ls"}},
                                   {"type": "tool_use", "id": "t_bash_raw",
                                    "name": "Bash", "input": {}},
                                   # cli either way: installed → non-OS dir,
                                   # or absent from PATH entirely
                                   {"type": "tool_use", "id": "t_cli",
                                    "name": "Bash",
                                    "input": {"command": "vercel deploy"}}]}),
        # typed slash commands: usage evidence rows; /clear is builtin noise
        _line(type="user", uuid="u3", timestamp="2026-07-07T14:00:30.000Z",
              message={"role": "user", "content":
                       "<command-name>/pm-execution:write-prd</command-name>"
                       "<command-args>kick off</command-args>"}),
        _line(type="user", uuid="u4", timestamp="2026-07-07T14:00:40.000Z",
              message={"role": "user", "content": [{"type": "text", "text":
                       "<command-name>/clear</command-name>"}]}),
        # known-ignored event type: not drift
        _line(type="queue-operation", timestamp="2026-07-07T14:01:01.000Z"),
        # unknown event type: drift
        _line(type="weird-event", timestamp="2026-07-07T14:01:02.000Z"),
        # malformed line
        '{"type": "assistant", "truncated...',
    ]
    f.write_text("\n".join(lines) + "\n")
    # subagent file
    sub = proj / "11111111-1111-1111-1111-111111111111" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-abc.jsonl").write_text(_line(
        type="assistant", uuid="s1", timestamp="2026-07-07T14:02:00.000Z",
        message={"role": "assistant", "model": "claude-haiku-4-5",
                 "usage": {"input_tokens": 3, "output_tokens": 9},
                 "content": [{"type": "text", "text": "hi"}]}) + "\n")
    return f


class TestIngest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "projects"
        self.db_path = Path(self.tmp.name) / "test.db"
        build_fixture(self.root)
        self.summary = ingest.sync(projects_root=self.root, db_path=self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def q(self, sql, *args):
        return self.conn.execute(sql, args).fetchall()

    def test_usage_preserved_verbatim(self):
        r = self.q("SELECT * FROM messages WHERE uuid='a1'")[0]
        self.assertEqual(r["input_tokens"], 12)
        self.assertEqual(r["output_tokens"], 340)
        self.assertEqual(r["cache_read_tokens"], 39810)
        self.assertEqual(r["cache_create_tokens"], 1200)
        u1 = self.q("SELECT * FROM messages WHERE uuid='u1'")[0]
        self.assertIsNone(u1["input_tokens"])  # NULL, never zero-filled

    def test_consumer_classification(self):
        skill = self.q("SELECT * FROM tool_calls WHERE tool_use_id='t_skill'")[0]
        self.assertEqual(skill["consumer_type"], "skill")
        self.assertEqual(skill["consumer"], "pm-execution:write-prd")
        mcp = self.q("SELECT * FROM tool_calls WHERE tool_use_id='t_mcp'")[0]
        self.assertEqual(mcp["consumer_type"], "mcp")
        self.assertEqual(mcp["consumer"], "plugin_playwright_playwright")
        self.assertEqual(mcp["mcp_tool"], "browser_navigate")
        bash = self.q("SELECT * FROM tool_calls WHERE tool_use_id='t_bash'")[0]
        self.assertEqual(bash["consumer_type"], "shell")  # /bin/ls is OS-shipped
        self.assertEqual(bash["consumer"], "ls")
        self.assertEqual(bash["tool"], "Bash")
        raw = self.q("SELECT * FROM tool_calls WHERE tool_use_id='t_bash_raw'")[0]
        self.assertEqual(raw["consumer_type"], "builtin")  # honest fallback
        self.assertEqual(raw["consumer"], "Bash")

    def test_command_tags_recorded(self):
        rows = self.q("SELECT * FROM tool_calls WHERE consumer_type='command'")
        by = {r["consumer"]: r for r in rows}
        self.assertIn("pm-execution:write-prd", by)  # slash stripped
        self.assertIn("clear", by)  # recorded; matches no file, so invisible
        r = by["pm-execution:write-prd"]
        self.assertEqual(r["tool"], "command")
        self.assertTrue(r["tool_use_id"].startswith("cmd:"))
        self.assertIsNone(r["duration_ms"])
        # deterministic ids: resync must not duplicate
        n0 = len(rows)
        f = next(iter((self.root / "-Users-me-code-demo").glob("*.jsonl")))
        f.touch()
        ingest.sync(projects_root=self.root, db_path=self.db_path)
        self.assertEqual(len(self.q(
            "SELECT * FROM tool_calls WHERE consumer_type='command'")), n0)

    def test_pairing_and_orphan(self):
        mcp = self.q("SELECT * FROM tool_calls WHERE tool_use_id='t_mcp'")[0]
        self.assertEqual(mcp["duration_ms"], 4200)
        self.assertEqual(mcp["error"], 0)
        bash = self.q("SELECT * FROM tool_calls WHERE tool_use_id='t_bash'")[0]
        self.assertIsNone(bash["duration_ms"])  # orphan stays NULL

    def test_drift_and_bad_lines(self):
        self.assertEqual(self.summary["bad_lines"], 1)
        self.assertEqual(self.summary["unknown_types"].get("weird-event"), 1)
        self.assertNotIn("queue-operation", self.summary["unknown_types"])
        self.assertIn("brand_new_field", self.summary["unknown_fields"])

    def test_cwd_captured_first_seen(self):
        r = self.q("SELECT cwd FROM sessions WHERE parent_session IS NULL")[0]
        self.assertEqual(r["cwd"], "/Users/me/code/demo")
        sub = self.q("SELECT cwd FROM sessions WHERE parent_session IS NOT NULL")[0]
        self.assertIsNone(sub["cwd"])  # subagent fixture has no cwd -> NULL

    def test_subagent_linked_to_parent(self):
        r = self.q("SELECT * FROM sessions WHERE parent_session IS NOT NULL")[0]
        self.assertEqual(r["parent_session"],
                         "11111111-1111-1111-1111-111111111111")
        # namespaced by parent: twin agent ids under two parents never collide
        self.assertEqual(r["session_id"],
                         "11111111-1111-1111-1111-111111111111/agent-abc")

    def test_line_no_links_tool_to_exact_message(self):
        r = self.q("SELECT m.output_tokens o FROM tool_calls tc "
                   "JOIN messages m ON m.session_id=tc.session_id "
                   "AND m.line_no=tc.line_no WHERE tc.tool_use_id='t_skill'")[0]
        self.assertEqual(r["o"], 340)

    def test_old_schema_store_rebuilds(self):
        c = sqlite3.connect(self.db_path)
        c.execute("UPDATE meta SET value='0' WHERE key='schema_version'")
        c.commit(); c.close()
        s = ingest.sync(projects_root=self.root, db_path=self.db_path)
        self.assertGreater(s["files_parsed"], 0)  # cache rebuilt from scratch

    def test_resync_is_idempotent_and_skips(self):
        before = self.q("SELECT COUNT(*) c FROM messages")[0]["c"]
        s2 = ingest.sync(projects_root=self.root, db_path=self.db_path)
        self.assertEqual(s2["files_parsed"], 0)  # mtime+size unchanged
        after = self.q("SELECT COUNT(*) c FROM messages")[0]["c"]
        self.assertEqual(before, after)


class TestCliProgram(unittest.TestCase):
    """Extraction heuristic contract (design.md): first acting program,
    wrappers skipped, honest None when unextractable."""

    def x(self, cmd):
        return ingest._cli_program(cmd)

    def test_plain_and_args(self):
        self.assertEqual(self.x("vercel deploy --prod"), "vercel")

    def test_cd_prefix_skipped(self):
        self.assertEqual(self.x("cd /Users/me/proj && vercel deploy"), "vercel")

    def test_env_and_wrappers_skipped(self):
        self.assertEqual(self.x("FOO=1 sudo nohup python3 -m x"), "python3")

    def test_npx_resolves_target(self):
        self.assertEqual(self.x("npx vercel deploy"), "vercel")

    def test_pnpm_dlx_resolves_target(self):
        self.assertEqual(self.x("pnpm dlx create-app my-app"), "create-app")

    def test_absolute_path_basename(self):
        self.assertEqual(self.x("/opt/homebrew/bin/openspec list --json"),
                         "openspec")

    def test_first_program_of_compound(self):
        self.assertEqual(self.x("git add . && git commit -m x"), "git")
        self.assertEqual(self.x("grep -rn pat | head -5"), "grep")

    def test_shell_keywords_never_programs(self):
        self.assertEqual(self.x("for f in a b; do rm $f; done"), "rm")
        self.assertEqual(self.x("if true; then echo y; fi"), "echo")

    def test_unextractable_is_none(self):
        self.assertIsNone(self.x(""))
        self.assertIsNone(self.x(None))
        self.assertIsNone(self.x("cd /somewhere"))
        self.assertIsNone(self.x('$(brew --prefix)/bin/tool run'))
        self.assertIsNone(self.x("-o output.txt"))  # stray flag, not a program


class TestCliKind(unittest.TestCase):
    """Provenance split: OS-shipped → shell, installed/absent → cli.
    Cache seeded so tests don't depend on this machine's PATH."""

    def setUp(self):
        self._saved = dict(ingest._kind_cache)
        ingest._kind_cache.clear()

    def tearDown(self):
        ingest._kind_cache.clear()
        ingest._kind_cache.update(self._saved)

    def test_os_binary_is_shell(self):
        self.assertEqual(ingest._cli_kind("grep",
                         which=lambda p: "/usr/bin/grep"), "shell")

    def test_installed_binary_is_cli(self):
        self.assertEqual(ingest._cli_kind("vercel",
                         which=lambda p: "/opt/homebrew/bin/vercel"), "cli")

    def test_absent_from_path_is_cli(self):
        self.assertEqual(ingest._cli_kind("goneware",
                         which=lambda p: None), "cli")

    def test_shell_builtin_is_shell(self):
        self.assertEqual(ingest._cli_kind("source",
                         which=lambda p: None), "shell")

    def test_result_is_cached(self):
        calls = []
        def w(p):
            calls.append(p)
            return "/usr/bin/sed"
        ingest._cli_kind("sed", which=w)
        ingest._cli_kind("sed", which=w)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
