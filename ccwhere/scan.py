"""Read-only filesystem scan: per-project standing-cost itemization and the
shared-floor estimate. Token sizes are size/4 estimates (kill-test #2 method);
the measured median carries authority — these numbers only guide pruning."""
import json
import os
import re
from pathlib import Path

HOME = Path.home()

_NOTES = {
    "CLAUDE.md": "Instructions file — loads in full when a session starts here",
    "AGENTS.md": "More instructions — loads in full alongside CLAUDE.md",
    ".mcp.json": "Connected tools (MCP) — their definitions load at session start",
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
                    "tokens": ((len(m.group(1)) if m else 0) + 40) // 4,
                    "file_tok": _tokens(sm)})
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
                    "tokens": ((len(m.group(1)) if m else 0) + 40) // 4,
                    "file_tok": _tokens(md)})
    return out


def _enabled_map(settings_path):
    """The enabledPlugins map from one settings file, or None if absent."""
    try:
        m = json.loads(settings_path.read_text()).get("enabledPlugins")
        return m if isinstance(m, dict) else None
    except (OSError, ValueError):
        return None


def _plugin_descs(home):
    """Registry: plugin key -> active-version skill/command descs."""
    out = {}
    try:
        installed = json.loads(
            (home / "plugins" / "installed_plugins.json").read_text())
        for key, entries in installed.get("plugins", {}).items():
            pkg = key.split("@")[0]
            descs = []
            for e in entries:
                p = Path(e.get("installPath", ""))
                if p.is_dir():
                    descs.extend(_skill_descs(p / "skills", pkg=pkg)
                                 if (p / "skills").is_dir()
                                 else _skill_descs(p, pkg=pkg))
                    descs.extend(_command_descs(p / "commands", pkg=pkg))
            out[key] = descs
    except (OSError, ValueError):
        pass
    return out


def _user_enabled_keys(reg, home):
    """Plugin keys loading at user scope. Enablement is per-scope
    (enabledPlugins in settings.json); a missing key at user scope means an
    older config where installed = loaded — never report a false zero."""
    user = _enabled_map(home / "settings.json")
    return list(reg) if user is None else [k for k in reg if user.get(k)]


# Discovery rules, settled by probe sessions (2026-07-09/10; token
# measurement plus having probes enumerate their visible skills):
# .claude skill tiers on the vertical path through the session's cwd are
# visible (ancestors and descendants; siblings are not); project plugin
# enablement resolves strictly at cwd/.claude; and the eager context cost
# per entry is a small stub (see EAGER_STUB_TOK), not the description.
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
              "dist", ".next"}


def _tier_descs(d):
    cl = d / ".claude"
    descs = (_skill_descs(cl / "skills", pkg=d.name)
             if (cl / "skills").is_dir() else [])
    descs.extend(_command_descs(cl / "commands", pkg=d.name))
    return descs


# Eager cost per skill/command/plugin entry, calibrated from probe sessions
# (2026-07-09/10): a planted 2,170-token description raised first-call
# context by 46 tok; at scale 13-26 tok/entry. Descriptions are an on-use
# catalog, NOT an eager tax — the desc/4 sizes remain as "catalog".
EAGER_STUB_TOK = 25


def _instruction_items(d, home=None, project_dirname=None):
    """Eagerly-loaded files at one folder: instruction files at full size."""
    items = []
    for name, note in _NOTES.items():
        t = _tokens(d / name)
        if t:
            items.append({"name": name, "tokens": t, "note": note,
                          "tag": "prunable"})
    if home and project_dirname:
        t = _tokens(home / "projects" / project_dirname / "memory"
                    / "MEMORY.md")
        if t:
            items.append({"name": "memory/MEMORY.md", "tokens": t,
                          "note": "Claude's saved memory for this project — loads every session",
                          "tag": "prunable"})
    return items


def _stub_item(name, descs, note):
    return {"name": f"{name} ({len(descs)})",
            "tokens": EAGER_STUB_TOK * len(descs),
            "catalog": sum(x["tokens"] for x in descs),
            "full": sum(x.get("file_tok", 0) for x in descs),
            "note": note, "tag": "prunable", "skills": descs}


def _dir_items(d, home, reg, user_keys, project_dirname=None):
    """Everything a session at/below this folder eagerly pays for it."""
    items = _instruction_items(d, home, project_dirname)
    descs = _tier_descs(d)
    if descs:
        items.append(_stub_item(".claude/skills+commands", descs,
                                "Small fixed cost per skill at start; the rest loads on use"))
    merged = {}
    for nm in ("settings.json", "settings.local.json"):
        m = _enabled_map(d / ".claude" / nm)
        if m:
            merged.update(m)
    keys = [k for k, v in merged.items() if v and k in reg
            and k not in user_keys]
    pdescs = [x for k in keys for x in reg[k]]
    if pdescs:
        items.append(_stub_item("plugins enabled here", pdescs,
                                "Plugins switched on for this folder —"
                                " small fixed cost each at start"))
    return items


def _has_content(d):
    return any(_tokens(d / n) for n in _NOTES) or (d / ".claude").is_dir()


def _dormant_dirs(keep):
    """Content-bearing subfolders of observed session roots that were never
    themselves a session root: present on disk, never loaded — so no
    measured token load exists for them."""
    found = {}
    for base in list(keep.values()):
        for root, dirs, _ in os.walk(base):
            dirs[:] = [x for x in dirs
                       if not x.startswith(".") and x not in _SKIP_DIRS]
            for x in dirs:
                p = Path(root, x)
                if str(p) not in keep and _has_content(p):
                    found[str(p)] = p
    return found


def context_tree(projects, claude_home=None, stop_at=None):
    """The ledger's explanatory layer: folders from user scope down each
    observed session path, with 'additional' eager tokens per level and
    'accumulated' along the branch. Single-branch model by design: visiting
    sibling folders mid-session loads their content on use — not modeled."""
    home = Path(claude_home) if claude_home else HOME / ".claude"
    stop = Path(stop_at) if stop_at else Path.home()
    reg = _plugin_descs(home)
    user_keys = _user_enabled_keys(reg, home)

    uitems = []
    t = _tokens(home / "CLAUDE.md")
    if t:
        uitems.append({"name": "~/.claude/CLAUDE.md", "tokens": t,
                       "note": "Your personal instructions — load in every session",
                       "tag": "prunable"})
    udescs = (_skill_descs(home / "skills", pkg="(user)")
              if (home / "skills").is_dir() else [])
    udescs.extend(_command_descs(home / "commands", pkg="(user)"))
    if udescs:
        uitems.append(_stub_item("~/.claude/skills+commands", udescs,
                                 "Load in every session — small fixed"
                                 " cost each at start"))
    pdescs = [x for k in user_keys for x in reg[k]]
    if pdescs:
        uitems.append(_stub_item("user plugins", pdescs,
                                 "Switched on everywhere — small fixed"
                                 " cost each at start"))
    hidden = len(reg) - len(user_keys)
    if hidden > 0:
        uitems.append({"name": f"installed, switched on per-folder"
                               f" ({hidden} plugins)", "tokens": None,
                       "note": "Installed, but only switched on in specific"
                               " folders — counted under those folders"
                               " below",
                       "tag": "info"})
    uitems.append({"name": "Claude Code overhead", "tokens": None,
                   "note": "System prompt and built-in tools — a real cost"
                           " in every session, but not visible as files;"
                           " see the footnote", "tag": "fixed"})
    uadd = sum(i["tokens"] or 0 for i in uitems)
    nodes = [{"path": "~", "label": "user level (~/.claude)", "depth": 0,
              "additional": uadd, "accumulated": uadd,
              "median": None, "n": None, "items": uitems}]

    med = {}
    for p in projects:
        if p.get("cwd"):
            med[str(Path(p["cwd"]))] = (p["median"], p["n"], p["project"])

    keep = {}
    for p in projects:
        if not p.get("cwd"):
            continue
        c = Path(p["cwd"])
        chain = []
        for d in [c] + list(c.parents):
            if d == stop or d == d.parent:
                break
            chain.append(d)
        for d in chain:
            if d == c or _has_content(d):
                keep[str(d)] = d

    dorm = _dormant_dirs(keep)
    order = sorted(set(keep) | set(dorm))
    acc = {"~": uadd}
    depth_of = {"~": 0}
    for key in order:
        dormant = key not in keep
        d = dorm[key] if dormant else keep[key]
        m = med.get(key, (None, None, None))
        items = _dir_items(d, home, reg, user_keys, project_dirname=m[2])
        if dormant and not items:
            continue
        parent = "~"
        for anc in d.parents:
            if str(anc) in depth_of:
                parent = str(anc)
                break
        depth = depth_of[parent] + 1
        depth_of[key] = depth
        base = Path(parent) if parent != "~" else None
        label = str(d.relative_to(base)) if base else \
            str(d).replace(str(Path.home()), "~")
        if dormant:
            # ponytail: item sizes stay as file facts (what a session opened
            # here WOULD add); node columns stay empty — nothing measured.
            nodes.append({"path": key, "label": label, "depth": depth,
                          "additional": None, "accumulated": None,
                          "median": None, "n": None, "dormant": True,
                          "items": items})
            continue
        add = sum(i["tokens"] or 0 for i in items)
        accumulated = acc[parent] + add
        acc[key] = accumulated
        nodes.append({"path": key, "label": label, "depth": depth,
                      "additional": add, "accumulated": accumulated,
                      "median": m[0], "n": m[1], "items": items})
    return nodes
