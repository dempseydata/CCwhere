# ccwhere

**See where your tokens got burned.**

Every Claude Code session starts tens of thousands of tokens deep before you type a word — skill descriptions, instructions, MCP schemas, plugins you forgot you installed. Cost tools tell you *how much* you spent; ccwhere is the diagnosis layer that tells you *where and why*: which skills, MCP servers, and CLI programs actually earn their context, what every project pays before work starts, and — with usage evidence per installed item — what to review for pruning. Its first real finding paid for itself: a never-used plugin silently taxing every session 3,000+ tokens, uninstalled the same afternoon.

And it refuses to fabricate a number to get there: attribution is genuinely ambiguous, so two lenses are always shown and never averaged; context no file explains renders as *unattributed* at full size; thin evidence is badged, not hidden. Zero dependencies, read-only, one process — nothing leaves your machine.

## What it shows

- **Consumption** — daily token flow with drill-down to hour and event level, and a league table of consumers ranked under *two* attribution lenses (session-level and message-level), shown side by side and never averaged. Agreement between the lenses is the signal; disagreement is flagged, not hidden.
- **Context ledger** — what every project pays before any work happens. The measured first-call median is the authoritative number; a best-effort file itemization (CLAUDE.md, skills, memory, plugins) sits beneath it, and the share no file explains is shown at full size as *unattributed* — never normalized away. Drills to a per-skill pruning list: standing cost, usage history, first/last used, never-used headline.
- **Performance** — p50/p95/max latency and error rates per tool (MCP servers broken out per tool), computed over paired tool calls only. Orphaned calls count as calls, never as fabricated durations.
- **Live** — what is running right now, from file mtimes at request time, independent of sync. Read-only by design: no kill, pause, or navigate controls exist.

## Why token attribution is ambiguous — and what the two lenses are

There is no true answer to "how many tokens did this skill cost me", because context is shared. Suppose a 2M-token session invoked a skill exactly once. Charge the skill the whole session and you've blamed it for work it never touched. Charge it only the one message that invoked it and you've missed its real cost — the output it produced shaped every message that followed. Any single number between those two extremes is an editorial choice dressed up as measurement.

So ccwhere shows the two defensible bounds and refuses to blend them:

- **Session lens** — the total tokens of every session the consumer appeared in. An upper bound; reads high, because one long session inflates everything it touched.
- **Message lens** — only the tokens of the exact messages that invoked it. A lower bound; reads low, because a consumer's real cost lands downstream of the call.

The signal is **agreement**: a consumer ranked top-5 under both lenses is genuinely expensive, and gets flagged as such. Disagreement — high on one lens, low on the other — is flagged too, and usually means a long-session artifact rather than a real burner: inspect before acting. Averaging the lenses would manufacture precision that does not exist, and is banned in the spec.

## Principles

1. **Honest numbers.** No single "tokens burned by X" figure exists (see above). Unattributed context is displayed, not hidden. Low samples are badged, not dropped.
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
