# jsonl-ingest

## Purpose
Parse `~/.claude/projects` JSONL history into the event store: fault-tolerant, drift-aware, classification at ingest.

## Requirements

### Requirement: Full-history backfill
On first run against an empty store, ingest SHALL parse every session file under `~/.claude/projects/**/*.jsonl`, including subagent files (`**/subagents/agent-*.jsonl`, linked to their parent session), read-only, completing the reference machine's history (~266 files) in under 60 seconds.

#### Scenario: First run fills the store
- **WHEN** ingest runs against an empty database
- **THEN** all session files across all projects are parsed and message, tool-call, and session rows exist for each

#### Scenario: Subagent files attach to parents
- **WHEN** a session directory contains `subagents/agent-*.jsonl`
- **THEN** those events are ingested with the parent session id recorded

### Requirement: Incremental sync is operator-triggered and cheap
Subsequent syncs SHALL re-parse only files whose mtime or size changed since their sync state, and SHALL be triggered by an explicit call (manual refresh default per PRD story 8), never by a background timer inside the ingest layer.

#### Scenario: Only the active session re-parses
- **WHEN** one session file grew since the last sync and 265 did not
- **THEN** exactly that one file is re-parsed and its rows upserted

### Requirement: Fault tolerance per line
A malformed or unparseable JSONL line SHALL be counted and skipped without aborting the file or the sync. One corrupt session file SHALL NOT prevent other files from syncing.

#### Scenario: Bad line, sync survives
- **WHEN** a file contains a truncated JSON line mid-file
- **THEN** remaining lines still ingest and the failure is reflected in drift/skip counters

### Requirement: Unknown data feeds the drift canary
Event types and message fields not recognized by the parser SHALL be counted per sync (feeding the event-store drift counters) and skipped without error. Recognized-but-new usage fields SHALL NOT corrupt stored known fields.

#### Scenario: New event type appears after a Claude Code update
- **WHEN** a sync encounters an event type the parser has no handler for
- **THEN** the event is skipped, the unknown-type counter increments, and the sync completes normally

### Requirement: Consumer classification at ingest
Each tool_use SHALL be classified at ingest per CONTEXT.md: `Skill` (from Skill tool input, exact skill name preserved), `MCP server` (parsed from `mcp__<server>__<tool>` names, server captured), `CLI program` / `Shell utility` (a Bash tool_use whose command string yields a program via the extraction heuristic: leading `cd` segments dropped, env assignments and wrappers — sudo, nohup, time, command, exec, env, shell keywords — skipped, `npx`/`pnpm dlx` resolved to their target, basename taken, first acting program wins; the program is then resolved by PATH provenance — binaries in OS directories (`/bin`, `/usr/bin`, `/sbin`, `/usr/sbin`) and shell builtins classify as `shell`, everything else — installed binaries, scripts, programs absent from PATH — as `cli`; tool name `Bash` retained), or `Built-in tool` (everything else, tool name as identity). A Bash command from which no program can be extracted SHALL classify as built-in `Bash` — never a guessed program. Provenance SHALL come from the machine, never a hand-curated command list.

#### Scenario: MCP name parsed to server
- **WHEN** a tool_use named `mcp__plugin_playwright_playwright__browser_navigate` is ingested
- **THEN** its Consumer is MCP server `plugin_playwright_playwright` with tool `browser_navigate` retained for Performance queries

#### Scenario: Skill identity preserved
- **WHEN** the Skill tool is invoked with `skill: "pm-execution:write-prd"`
- **THEN** the Consumer is Skill `pm-execution:write-prd`

#### Scenario: Installed program classifies cli through wrappers
- **WHEN** a Bash tool_use runs `cd /Users/me/proj && npx vercel deploy --prod` and `vercel` resolves outside the OS directories (or not at all)
- **THEN** its Consumer is CLI program `vercel`

#### Scenario: OS-shipped utility classifies shell
- **WHEN** a Bash tool_use runs `grep -rn pattern .` and `grep` resolves to `/usr/bin/grep`
- **THEN** its Consumer is Shell utility `grep`

#### Scenario: Unextractable command stays honest
- **WHEN** a Bash tool_use runs a command the heuristic cannot resolve to a program
- **THEN** it classifies as built-in `Bash`, never a fabricated program name

### Requirement: Callable sync entry point
Ingest SHALL expose a single callable entry (used later by the CLI/server) and a `python -m` invocation for standalone verification, both returning a sync summary: files scanned, files parsed, events added, unknown counts, elapsed time.

#### Scenario: Sync reports its work
- **WHEN** the module entry point runs against real history
- **THEN** it prints/returns a summary with non-zero files parsed and the drift share

### Requirement: Command invocations recorded from command-name tags
Ingest SHALL record each `<command-name>` tag found in user-message content as a tool-call row with `consumer_type='command'`, the command name stripped of its leading slash as consumer, tool name `command`, and a deterministic synthesized id (session, line, ordinal) so re-syncs stay idempotent. These rows are usage evidence for the ledger's pruning list, not league Consumers. Built-in commands are excluded from pruning guidance not by a curated list but structurally: only entries backed by a file on disk are itemized, and built-ins have none.

#### Scenario: Typed command counts as usage
- **WHEN** a user message contains `<command-name>/pm-execution:write-prd</command-name>`
- **THEN** a command row for `pm-execution:write-prd` exists and the ledger drill counts it toward that command's usage

#### Scenario: Built-in commands stay out of pruning guidance
- **WHEN** `/clear` was typed seven times
- **THEN** no drill entry shows it — no file on disk backs it — and it appears in no league view
