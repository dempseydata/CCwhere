# context-ledger-tab

## Purpose
Show what every session pays before work starts: measured medians, honest decomposition, and pruning evidence.

## Requirements

### Requirement: Measured median is the authoritative number
The ledger SHALL compute, per project, the median first-call context of its parent sessions (subagent sessions excluded): the first message in each session carrying usage, summing input + cache-read + cache-creation tokens. This measured number is authoritative; no static estimate may replace or adjust it. Projects with fewer than 3 measured sessions SHALL carry a low-sample badge, never be hidden.

#### Scenario: Median over parent sessions only
- **WHEN** a project has 10 parent sessions and 200 subagent sessions
- **THEN** its median is computed over the 10 parent sessions

### Requirement: Eager stubs, not descriptions
Skill, command, and plugin entries SHALL be costed eagerly at a calibrated per-entry stub (25 tok; probe-measured 2026-07-09/10 — a planted 2,170-token description raised first-call context by 46 tokens; 13–46/entry at scale), never at description size. Description sizes SHALL be shown as the secondary "descriptions (on use)" number, full SKILL.md/command body sizes as "bodies (when invoked)" — the three-tier cost truth (stub → description → body) — and descriptions remain the basis of the pruning drill, which also shows each entry's body size. Instruction files (CLAUDE.md, AGENTS.md, .mcp.json, project memory) count eagerly at full size.

#### Scenario: A huge description is not an eager tax
- **WHEN** an installed skill carries a 2,000-token description
- **THEN** its eager itemization is the calibrated stub, with the description size shown as catalog-on-use

### Requirement: Context tree with additional and accumulated
The ledger SHALL render a folder tree from the user scope down each observed session path (content-less intermediate folders skipped): per node, "additional" eager tokens introduced at that level and "accumulated" — the parent's accumulated plus additional, along one branch. Nodes with sessions SHALL show the measured median and the unattributed share (median − accumulated, clamped at zero) beside the estimate, with low-sample badges under N=3. Each node SHALL expand to its items (instruction files, stubs with catalogs, project-enabled plugins) and onward into the per-skill usage drill. The UI SHALL state the single-branch assumption — visiting a sibling folder mid-session loads its content on use, not modeled — and the stub calibration with its measured range.

#### Scenario: Accumulation follows the branch
- **WHEN** a project folder adds 1,000 tokens of instruction files below a user level of 200
- **THEN** its accumulated shows 1,200, and a subfolder with 500 more shows 1,700

#### Scenario: Probe self-validation
- **WHEN** a session ran in a bare folder containing one skill
- **THEN** its node shows additional = one stub and its measured median sits beside it, the difference appearing as unattributed

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
