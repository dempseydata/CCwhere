# context-ledger-tab

## Purpose
Show what every session pays before work starts: measured medians, honest decomposition, and pruning evidence.

## Requirements

### Requirement: Measured median is the authoritative number
The ledger SHALL compute, per project, the median first-call context of its parent sessions (subagent sessions excluded): the first message in each session carrying usage, summing input + cache-read + cache-creation tokens. This measured number is authoritative; no static estimate may replace or adjust it. Projects with fewer than 3 measured sessions SHALL carry a low-sample badge, never be hidden.

#### Scenario: Median over parent sessions only
- **WHEN** a project has 10 parent sessions and 200 subagent sessions
- **THEN** its median is computed over the 10 parent sessions

### Requirement: Calibrated floor and honest decomposition
The ledger SHALL derive the calibrated floor (minimum median across projects) and decompose each project's median as floor + itemized + unattributed, where unattributed = median − floor − itemized (clamped at zero) and is always displayed at full size. The shared floor SHALL show its own best-effort decomposition of everything loaded at user level regardless of project: `~/.claude/CLAUDE.md`, user-scoped `~/.claude/skills` and `~/.claude/commands` descriptions, active plugin skill and command descriptions (from `installed_plugins.json`, active versions only — raw cache scans double-count) as `prunable`, and the harness base as `fixed cost` with no fabricated number.

#### Scenario: Unattributed never hidden
- **WHEN** a project's itemized files explain 65% of its median
- **THEN** the remaining share renders as an explicit unattributed segment with named suspects (session hooks, MCP instructions, harness lists)

### Requirement: Static itemization from the project's real path
Using the session-recorded cwd, the ledger SHALL itemize on-disk standing costs per project: root CLAUDE.md, AGENTS.md, project `.claude/skills` descriptions, project memory, `.mcp.json` — each with an estimated token size (size/4), a plain-language note, and a `prunable` tag. Scanning is read-only; a missing or inaccessible path yields an empty itemization, never an error. Pruning tags SHALL attach only to itemized entries.

#### Scenario: Itemization matches the hand-measured method
- **WHEN** the ledger scans a project carrying a root CLAUDE.md and AGENTS.md
- **THEN** each appears as a separate prunable entry with a size/4 token estimate consistent with hand measurement

### Requirement: Aggregate skill entries drill to usage evidence
Aggregate itemized entries ("plugin skill descriptions (N)", ".claude/skills (N)") SHALL expand to per-skill rows, each carrying: skill name (with package), description-token cost, total uses, a 14-day usage sparkline, first-used and last-used dates, and a status tag (`never used` / `stale >30d` / `active`) — usage matched from the union of Skill-tool invocations and typed command invocations (`<command-name>` rows) in the store, since skill-backed commands are invoked both ways. Clicking a drill row's sparkline SHALL toggle an inserted full-width row beneath it with an enlarged version — dated x axis, readable y axis — offering the same invocations/tokens mode toggle as the league zoom; typed-command rows honestly show near-zero direct message tokens (user messages carry no usage block). Closed by a second click. Rows SHALL be grouped by package (so a skill maps to its source), each group headed by a visually distinct band (the package must be identifiable at a glance while scrolling) carrying its subtotal (skill count, standing cost, never-used cost); groups SHALL be ordered by never-used cost descending — the most wasteful package first — and rows within a group as a prune-priority list: never-used first (largest cost first), then by ascending use. The user-level section SHALL surface the total never-used cost as a headline number. A `prunable` tag without usage evidence is guidance-free and SHALL NOT be the drill floor for skill aggregates.

#### Scenario: Dead weight surfaces first
- **WHEN** the operator expands the plugin skills & commands entry
- **THEN** the top rows are the never-used skills with the largest description cost, each showing zero uses and no dates

#### Scenario: Typed command usage prevents false pruning advice
- **WHEN** a command was invoked only by typing its slash command, never via the Skill tool
- **THEN** its drill row shows that usage — it is not marked `never used`

#### Scenario: Drill sparkline enlarges in place
- **WHEN** the operator clicks a drill row's sparkline
- **THEN** a full-width row opens beneath it with the enlarged dated chart; a second click closes it

### Requirement: Ledger UI per the design contract
The tab SHALL render the user-level inventory once, above the project list — this payload applies to every session on the machine and SHALL NOT be repeated inside each project's expansion. Per-project rows follow — honest label from cwd, median as the big number, composition bar (floor gray / itemized ink / unattributed hatch) — each expanding to a two-group inventory (this project's files, unattributed), per `design/mockups/context-ledger-tab.html`. Composition bars share one scale (the maximum median) so projects compare by eye.

#### Scenario: Expand to inventory
- **WHEN** the operator clicks a project row
- **THEN** the two-group inventory (project files, unattributed) opens beneath it with per-item bars, notes, and tags; clicking again closes it — the user-level section stays at the top, rendered once
