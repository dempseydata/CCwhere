# ccwhere

**See where your tokens got burned.**

Every Claude Code session starts tens of thousands of tokens deep before you type a word — skill descriptions, instructions, MCP schemas, plugins you forgot you installed. Cost tools tell you *how much* you spent; ccwhere is the diagnosis layer that tells you *where and why*: which skills, MCP servers, and CLI programs actually earn their context, what every project pays before work starts, and — with usage evidence per installed item — what to review for pruning. Its first real finding paid for itself: a never-used plugin silently taxing every session 3,000+ tokens, uninstalled the same afternoon.

And it refuses to fabricate a number to get there: attribution is genuinely ambiguous, so two lenses are always shown and never averaged; context no file explains renders as *unattributed* at full size; thin evidence is badged, not hidden. Zero dependencies, read-only, one process — nothing leaves your machine.

## What it shows

- **Consumption** — daily token flow with drill-down to hour and event level, and a league table of consumers ranked under *two* attribution lenses (session-level and message-level), shown side by side and never averaged. Agreement between the lenses is the signal; disagreement is flagged, not hidden.
- **Context ledger** — what every project pays before any work happens. The measured first-call median is the authoritative number; a best-effort file itemization (CLAUDE.md, skills, memory, plugins) sits beneath it, and the share no file explains is shown at full size as *unattributed* — never normalized away. Drills to a per-skill pruning list: standing cost, usage history, first/last used, never-used headline.
- **Performance** — p50/p95/max latency and error rates per tool (MCP servers broken out per tool), computed over paired tool calls only. Orphaned calls count as calls, never as fabricated durations.
- **Live** — what is running right now, from file mtimes at request time, independent of sync. Read-only by design: no kill, pause, or navigate controls exist.

## Principles

1. **Honest numbers.** No single "tokens burned by X" figure exists — attribution is genuinely ambiguous, so both lenses are always shown. Unattributed context is displayed, not hidden. Low samples are badged, not dropped.
2. **Read-only.** ccwhere reads `~/.claude/projects` session history and never writes to it. It is a visibility layer — no task queues, no scheduling, no orchestration.
3. **Disposable cache.** Parsed history lives in `~/.ccwhere/ccwhere.db`. On any schema change it is deleted and rebuilt from source in about a second. There are no migrations.
4. **Drift canary.** When Claude Code's file format changes and events go unrecognized, a visible indicator says so. Silent omission is banned.

## Install & run

Requires Python 3.10+. No dependencies.

```sh
pip install git+https://github.com/dempseydata/CCwhere
ccwhere
```

Or from a clone:

```sh
git clone https://github.com/dempseydata/CCwhere && cd CCwhere
python3 -m ccwhere
```

The dashboard opens at `http://127.0.0.1:8917` (`--port` to change, `--no-browser` to suppress). Refresh is manual by default — you control when data syncs — with an optional 30-second auto-refresh toggle.

## Data & privacy

- Reads: `~/.claude/projects/**/*.jsonl` (read-only) and, for the Live tab's open-window count, the local process table (`ps`/`lsof`; degrades silently where unavailable).
- Writes: `~/.ccwhere/` only — the disposable cache plus `overrides.json`, the human-readable file behind the "demote to shell utilities" control.
- Network: none. The server binds to 127.0.0.1.

## Notes

- Consumer classification (skill / MCP server / CLI program / shell utility / built-in) happens at ingest; CLI programs are split from OS-shipped shell utilities by binary provenance, not by a curated list.
- Specifications for every capability live in `openspec/specs/` — the honest-numbers rules above are requirements there, not aspirations. System documentation (architecture, flows, permissions posture, configuration) lives in `documentation/`.
- Built and dogfooded by one operator; expect rough edges. Issues welcome.

## License

MIT
