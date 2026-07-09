# consumption-tab

## Purpose
Show where tokens flow: dual-lens league table, global filters, and drill-down to event-level evidence.

## Requirements

### Requirement: Dual-lens league table
The consumption view SHALL rank Consumers under both lenses per CONTEXT.md, computed over the active filters. The default view SHALL cover Skills, MCP servers, and CLI programs — the actionable Consumer types (installable, uninstallable, replaceable); built-in tools and shell utilities appear in nearly every session (Read, grep), so the Session lens hands them the whole corpus and they drown the ranking — and nothing can be pruned about them anyway. Visible toggles SHALL include built-ins and shell utilities on demand, independently. Lens computation runs over the active filters: **Session lens** (sum of total tokens of every session the Consumer appeared in, with session count) and **Message lens** (sum of tokens of the exact messages that invoked the Consumer, via stored line linkage). Both columns SHALL be shown, honestly named; no column may be titled "tokens burned by". The table SHALL be sortable by sessions and by either lens (descending); the default sort is the Message lens — direct message tokens (operator decision 2026-07-08). Rows SHALL carry: consumer, type tag, sessions, both lens values with length-encoded bars, a 14-day daily-invocation sparkline, and a flag — `both lenses` (top-5 on both), `lenses disagree` (top-5 on one, outside top-10 on the other), `N=1` (single session). Column headers and flags SHALL expose hover explanations stating what each lens is and which way it errs.

#### Scenario: Known rankings reproduced
- **WHEN** the league table is computed over all history on the reference machine in its default (skills + MCP + CLI) view
- **THEN** `plugin_playwright_playwright` ranks first on both lenses (kill-test #1 ground truth)

#### Scenario: Installed CLI programs rank by default
- **WHEN** the default league view renders on a machine where vercel and openspec were run through Bash
- **THEN** `vercel` and `openspec` appear as type-`cli` rows alongside skills and MCP servers, while `grep` and `ls` do not

#### Scenario: Built-ins and shell utilities on demand only
- **WHEN** the operator enables the "built-ins" or "shell utilities" toggle
- **THEN** those consumers join as league rows without altering the other rows' values

#### Scenario: MCP vs CLI comparison
- **WHEN** playwright work has run through both the playwright MCP server and the playwright CLI
- **THEN** both appear in the default view as separate league rows (types `mcp` and `cli`), directly comparable under either lens

#### Scenario: Disagreement flagged, never averaged
- **WHEN** a Consumer is top-5 on the Session lens but outside the top-10 on the Message lens
- **THEN** its row shows `lenses disagree` and no combined/average column exists

### Requirement: Global filter bar
One filter bar SHALL govern every panel on the consumption tab: time presets (today, yesterday, this week, last week, this month, 30d) plus a custom range, and a project multi-select. All bucketing SHALL use local time.

#### Scenario: Filters compose
- **WHEN** "last week" and two of five projects are selected
- **THEN** the strip, daily chart, and league table all reflect exactly that window and those projects

#### Scenario: Local-time day boundaries
- **WHEN** a session ran 23:30–00:30 local time
- **THEN** its tokens split across the two local days, never bucketed by UTC

### Requirement: At-a-glance strip with context
The strip SHALL show, for the active filters: total tokens with a delta vs the previous window of equal length; session count with the same comparison; top consumer (the Session-lens leader, marked if the Message lens agrees); cache hit rate — `cache_read / (input + cache_read + cache_create)` — rendered as a bullet graph against the 70% target. No number SHALL appear without its comparison (Few pitfall 2).

#### Scenario: Comparison window matches length
- **WHEN** the filter is a 7-day window
- **THEN** deltas compare against the immediately preceding 7 days

### Requirement: Daily chart with drill-down to evidence
The tab SHALL render a stacked daily bar chart of token components (cache read, input, output, cache create — fixed order, validated palette) via vendored Chart.js with one-time render animation. Clicking a day SHALL show that day's hourly bars; clicking an hour SHALL show the event list — sessions/consumers active in that hour with project, consumer, tokens, and duration — with breadcrumb navigation back up. The drill floor is the event list, never finer bars.

#### Scenario: Day to hour to events
- **WHEN** the operator clicks Tuesday, then 14:00
- **THEN** the view shows Tuesday's hourly bars, then a table of what actually ran 14:00–15:00, and the breadcrumb restores each level

### Requirement: Operator overrides on CLI consumers
The operator SHALL be able to demote any `cli` consumer to the shell-utilities bucket and restore it, from the league table itself: the type tag on a `cli` row is the demote control, and demoted rows — visible under the shell-utilities toggle — carry a visibly distinct tag marking them operator-demoted, which is the restore control. Under the shell-utilities toggle, demoted rows SHALL always be included in the table, pinned past any row cut, so every demoted item stays restorable in the UI (the earlier filter-area strip was removed as surplus — operator decision 2026-07-08). Overrides apply at query time only (the store keeps provenance truth) and persist in a human-readable file outside the disposable cache, surviving store rebuilds. Overrides SHALL apply only to `cli` consumers: skills and MCP servers are always actionable; shell and builtin are already on demand.

#### Scenario: Demote removes from default view instantly
- **WHEN** the operator clicks the type tag on the `npm` cli row
- **THEN** npm leaves the default league on the next fetch, no re-sync or rebuild, and `~/.ccwhere/overrides.json` lists it

#### Scenario: Demoted rows are pinned and restorable
- **WHEN** `npm` is demoted and ranks below the league's row cut
- **THEN** under the shell-utilities toggle npm still renders, with an operator-demoted tag distinct from provenance-shell rows, and clicking it restores npm to the default view

#### Scenario: Overrides survive a store rebuild
- **WHEN** the schema version bumps and the store is deleted and rebuilt
- **THEN** the demoted list is unchanged and still applies
