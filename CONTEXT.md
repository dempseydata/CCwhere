# ccwhere — CONTEXT

Glossary of canonical terms. Vocabulary only — no implementation details.
Decisions live in `docs/adr/`; requirements in `../definition/PRD.md`.

## Core

**Consumer** — anything that consumes tokens *and can be acted on* (uninstalled,
slimmed, replaced). The unit of the league table. Exactly five types:
**Skill**, **MCP server**, **CLI program**, **Shell utility**, **Built-in tool**.
The first three are actionable and rank by default; the last two are ubiquitous
and unprunable, shown on demand. Assistant prose costs tokens but is not a
Consumer — nothing can be done about it.

**Skill** — a named capability invokable in a session (e.g.
`pm-execution:write-prd`). One Consumer per skill name.

**MCP server** — a Model Context Protocol server. Tools roll up to their
server: the pruning decision is per-server, so the server is the Consumer.
Per-tool detail belongs to Performance, not the league table.

**Built-in tool** — a tool native to Claude Code (Read, Edit, Bash…). Each is
one Consumer.

**CLI program** — an *installed* command-line program identified by
classifying Bash commands at ingest (first acting program; `cd`, env prefixes,
and wrappers skipped; `npx` resolved to its target), so MCP-vs-CLI
substitutions (e.g. Playwright MCP vs Playwright CLI) can be compared even
when CLI use is not skill-mediated. A command yielding no program stays a
plain Bash built-in call.

**Shell utility** — an OS-shipped command (grep, ls, sed…), split from CLI
programs by provenance: the binary resolves inside the OS directories
(`/bin`, `/usr/bin`, `/sbin`, `/usr/sbin`) or is a shell builtin. Detected
from the machine, never a curated list. Unprunable, so shown on demand only.

**Demoted** — a CLI program the operator has moved into the shell-utilities
bucket (npm, node…). Operator-curated in the UI, persisted outside the
disposable cache, applied at query time; the store keeps provenance truth.
Applies to `cli` consumers only.

**Lens** — a named attribution heuristic. Two lenses, always shown together,
never averaged: the **Session lens** (a Consumer is credited the total tokens
of every session it appeared in — tends to overstate) and the **Message lens**
(a Consumer is credited only the tokens of messages that directly invoked it —
tends to understate). Agreement across lenses is the signal; disagreement is
flagged.

**Session** — one Claude Code conversation, recorded as one history file. A
**Live session** is one whose history changed within the last 5 minutes as of
the last sync; its row always shows relative last-activity time, so staleness
is self-describing. Older activity is history, not live.

**Project** — the working directory a session ran in; the grouping unit for
filters and the Context ledger.

**Event** — one parsed line of session history (message, tool call, tool
result…). The atomic unit ccwhere stores.

## Context ledger

**First-call context** — the context size of a session's first API call: what
the session paid before any work happened. The **Measured median** of first-call
context per project is the ledger's authoritative number.

**Standing cost** — tokens an installed item (skill descriptions, instruction
files) adds to every session in whose scope it loads.

**Calibrated floor** — the minimum measured median across all projects on the
machine; the machine-wide baseline every project pays regardless of its own files.

**Itemized** — the share of first-call context attributable to specific files
on disk. Only itemized entries may carry pruning guidance.

**Unattributed** — the share of first-call context no file on disk predicts.
Always shown at full size, never normalized away.

## Inventory

**Package** — the grouping of installed skills by origin: a plugin (active
version only), a project skills folder, or user scope.

**Prunable** — an installed item whose removal is both possible and
consequence-free by usage evidence (`never used`, or `stale >30d`).

**Stale** — used at least once, but not within the last 30 days.

## Mechanics

**Sync** — parsing new/changed session history into the store. **Backfill** is
the first sync, covering all existing history. Both are operator-triggered
(manual refresh default).

**Drift canary** — the visible indicator fed by counting unrecognized event
types/fields during sync; fires when the share exceeds a threshold. Silent
omission is banned.

**League table** — the Consumption tab's ranked table of Consumers under both
lenses.
