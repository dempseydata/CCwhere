"""Read-only filesystem scan: per-project standing-cost itemization and the
shared-floor estimate. Token sizes are size/4 estimates (kill-test #2 method);
the measured median carries authority — these numbers only guide pruning."""
import json
import re
from pathlib import Path

HOME = Path.home()

_NOTES = {
    "CLAUDE.md": "Project instructions at the working directory root",
    "AGENTS.md": "Agent conventions — loaded alongside CLAUDE.md",
    ".mcp.json": "Project MCP servers — schemas/instructions load in scope",
}


def _tokens(path: Path):
    try:
        return path.stat().st_size // 4
    except OSError:
        return 0


def _skill_descs(root: Path, pkg=None):
    """Per-skill description sizes (what actually loads every session)."""
    out = []
    for sm in root.rglob("SKILL.md"):
        try:
            head = sm.read_text(errors="ignore")[:3000]
        except OSError:
            continue
        m = re.search(r"^description:\s*(.+?)(?=\n\w|\n---)", head,
                      re.S | re.M)
        name = re.search(r"^name:\s*(.+)$", head, re.M)
        # frontmatter name and directory name can both differ from the
        # invocation name (e.g. dir write-prd, frontmatter create-prd) —
        # keep both as aliases for usage matching
        out.append({"name": (name.group(1).strip() if name
                             else sm.parent.name),
                    "dir": sm.parent.name,
                    "pkg": pkg,
                    "tokens": ((len(m.group(1)) if m else 0) + 40) // 4})
    return out


def _command_descs(root: Path, pkg=None):
    """Plugin/project commands: they load like skills and are invoked like
    skills (e.g. write-prd wraps the create-prd skill) — first-class entries."""
    out = []
    if not root.is_dir():
        return out
    for md in root.rglob("*.md"):
        try:
            head = md.read_text(errors="ignore")[:3000]
        except OSError:
            continue
        m = re.search(r"^description:\s*(.+?)(?=\n\w|\n---)", head,
                      re.S | re.M)
        out.append({"name": md.stem, "dir": md.stem, "pkg": pkg,
                    "kind": "command",
                    "tokens": ((len(m.group(1)) if m else 0) + 40) // 4})
    return out


def project_items(cwd, project_dirname, claude_home=None):
    """Itemized standing costs for one project. Missing paths yield nothing."""
    home = Path(claude_home) if claude_home else HOME / ".claude"
    items = []
    root = Path(cwd) if cwd else None
    if root and root.is_dir():
        for name, note in _NOTES.items():
            t = _tokens(root / name)
            if t:
                items.append({"name": name, "tokens": t, "note": note,
                              "tag": "prunable"})
        skills = root / ".claude" / "skills"
        if skills.is_dir():
            descs = _skill_descs(skills)
            descs.extend(_command_descs(root / ".claude" / "commands"))
            t = sum(d["tokens"] for d in descs)
            if t:
                items.append({"name": f".claude/skills+commands ({len(descs)})",
                              "tokens": t,
                              "note": "Project-scoped skill and command"
                                      " descriptions",
                              "tag": "prunable", "skills": descs})
    mem = home / "projects" / project_dirname / "memory" / "MEMORY.md"
    t = _tokens(mem)
    if t:
        items.append({"name": "memory/MEMORY.md", "tokens": t,
                      "note": "Persistent memory index for this project",
                      "tag": "prunable"})
    return items


def floor_items(claude_home=None):
    """Best-effort decomposition of the shared floor. Never invents numbers."""
    home = Path(claude_home) if claude_home else HOME / ".claude"
    items = []
    t = _tokens(home / "CLAUDE.md")
    if t:
        items.append({"name": "~/.claude/CLAUDE.md", "tokens": t,
                      "note": "User instructions — loaded into every session",
                      "tag": "prunable"})
    user_descs = (_skill_descs(home / "skills", pkg="(user)")
                  if (home / "skills").is_dir() else [])
    user_descs.extend(_command_descs(home / "commands", pkg="(user)"))
    t = sum(d["tokens"] for d in user_descs)
    if t:
        items.append({"name": f"~/.claude/skills+commands ({len(user_descs)})",
                      "tokens": t,
                      "note": "User-scoped skill and command descriptions —"
                              " loaded into every session",
                      "tag": "prunable", "skills": user_descs})
    descs = []
    try:
        installed = json.loads(
            (home / "plugins" / "installed_plugins.json").read_text())
        for key, entries in installed.get("plugins", {}).items():
            pkg = key.split("@")[0]
            for e in entries:
                p = Path(e.get("installPath", ""))
                if p.is_dir():
                    descs.extend(_skill_descs(p / "skills", pkg=pkg)
                                 if (p / "skills").is_dir()
                                 else _skill_descs(p, pkg=pkg))
                    descs.extend(_command_descs(p / "commands", pkg=pkg))
    except (OSError, ValueError):
        pass
    tok_total = sum(d["tokens"] for d in descs)
    if tok_total:
        items.append({"name": f"plugin skills & commands ({len(descs)})",
                      "tokens": tok_total,
                      "note": "Active plugin versions via installed_plugins.json"
                              " — loaded into every session",
                      "tag": "prunable", "skills": descs})
    items.append({"name": "harness base + tool schemas", "tokens": None,
                  "note": "System prompt, built-in tools, agent lists —"
                          " not itemizable from files",
                  "tag": "fixed"})
    return items
