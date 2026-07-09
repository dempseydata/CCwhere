# Architecture

## What this system is

ccwhere is a single-process, local-only observability dashboard for Claude Code. One Python process (stdlib only, zero runtime dependencies) parses Claude Code's session history into a disposable SQLite cache, serves a JSON API on localhost, and hosts a no-build static JS UI. It is a **visibility layer by constitution**: it observes, it never orchestrates.

## Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Runtime | Python ≥3.10, stdlib only | zero-install friction; nothing to audit but this repo |
| Store | SQLite (WAL), `~/.ccwhere/ccwhere.db` | disposable cache of JSONL truth; no migrations, ever |
| Server | `http.server.ThreadingHTTPServer`, 127.0.0.1 only | localhost is the trust boundary |
| UI | static JS, no build step; Chart.js v4 vendored | `git clone` is the whole toolchain |

## Data flow

```
~/.claude/projects/**/*.jsonl        (read-only source of truth)
        │  ingest.py — parse, classify consumers, pair tool calls
        ▼
~/.ccwhere/ccwhere.db                (disposable cache, schema-versioned)
        │  queries.py — dual-lens league, medians, percentiles
        ▼
server.py JSON API (127.0.0.1)  ───▶  ui/*.js tabs
```

Two paths deliberately bypass the store:

- **Live view** (`live.py`): request-time mtime scan + bounded file tail, plus a `ps`/`lsof` count of open Claude Code processes. "What is running" must not depend on when the operator last synced.
- **Ledger file scan** (`scan.py`): request-time read-only itemization of CLAUDE.md/skills/plugin descriptions on disk.

## Module map

| Module | Responsibility |
| --- | --- |
| `db.py` | schema + connection; disposable-cache rule (version mismatch → delete & rebuild); overrides file load/save |
| `ingest.py` | JSONL parsing, consumer classification (skill / mcp / cli / shell / command / builtin), tool-call pairing, drift counters |
| `queries.py` | all aggregation at query time: both lenses, medians, percentiles, filters |
| `scan.py` | static standing-cost itemization (size/4 estimates; measured numbers stay authoritative) |
| `live.py` | liveness bands + open-window process count |
| `server.py` | routes, `Cache-Control: no-store` everywhere, static traversal guard |
| `ui/filters.js` | shared presets/chips/tags/tooltips; each tab owns its own rendering |

## Trust boundaries

1. **Network**: binds 127.0.0.1 only; no outbound calls of any kind. The vendored Chart.js is the only third-party code.
2. **Filesystem reads**: `~/.claude/projects` (session history, read-only) and the plugin registry under `~/.claude/plugins`; Live additionally reads the process table via `ps`/`lsof` (degrades to absent on failure).
3. **Filesystem writes**: `~/.ccwhere/` only — the cache (deletable at any time) and `overrides.json` (operator curation, survives cache rebuilds).
4. **No auth exists** — see `permissions.md` for why that is the design, not an omission.

## Invariants worth defending in review

- The store is a cache: any schema change bumps `SCHEMA_VERSION` and triggers rebuild; migration code is banned.
- No fabricated numbers: orphaned tool calls carry NULL durations; unattributed context renders at full size; unextractable Bash commands stay `Bash`.
- Attribution is dual-lens and never averaged; rank-based flags are computed from data order, not display order.
- Read-only: no endpoint mutates anything outside `~/.ccwhere`.

## Related documents

- `flows.md` — the permission-relevant journeys and their side effects
- `permissions.md` — the (deliberately absent) authz model
- `variables.md` — configuration surface and secrets posture
- `../openspec/specs/` — binding requirements per capability
- `../docs/adr/0001-on-demand-process-not-daemon.md` — why no daemon
