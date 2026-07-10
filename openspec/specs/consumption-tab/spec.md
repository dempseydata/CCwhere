# consumption-tab

## Purpose
Show where tokens flow: dual-lens league table, global filters, and drill-down to event-level evidence.

## Requirements

### Requirement: Dual-lens league table
The consumption view SHALL rank Consumers under both lenses per CONTEXT.md, computed over the active filters. Consumer-type scope SHALL be controlled by five toggle chips rendered directly above the league table — they affect the league only, and sit with it: Skills, MCP servers, and CLI programs default ON (the actionable types); built-in tools and shell utilities default OFF, because they appear in nearly every session (Read, grep), the Session lens hands them the whole corpus, they drown the ranking — and nothing can be pruned about them anyway; the two default-off chips SHALL carry hover explanations of that rationale. Lens computation runs over the active filters: **Session lens** (sum of total tokens of every session the Consumer appeared in, with session count) and **Message lens** (sum of tokens of the exact messages that invoked the Consumer, via stored line linkage). Both columns SHALL be shown, honestly named; no column may be titled "tokens burned by". A PROVISIONAL counting toggle ("fresh work only", experimental — operator keep-or-kill pending, 2026-07-09) SHALL recompute both lenses and the agreement flags over input + output only, never blending modes; the toggle states its experimental status on hover. The table SHALL be sortable by sessions and by either lens (descending); the default sort is the Message lens — direct message tokens (operator decision 2026-07-08). Rows SHALL carry: consumer, type tag, sessions, both lens values with length-encoded bars, a 14-day daily-invocation sparkline (column labelled "uses · last 14 days"), and a flag — `high on both counts` (top-5 on both), `counts disagree` (top-5 on one, outside top-10 on the other), `seen once` (single session). Clicking a row's sparkline SHALL toggle an inserted full-width row beneath it with an enlarged version of the same 14 days — dated x axis, readable y axis — offering a mode toggle between uses/day and direct message tokens/day (the Message-lens tokens of the exact invoking messages, per local day); closed by a second click; enlarging never alters other rows. Column headers and flags SHALL expose hover explanations stating what each lens is and which way it errs.

#### Scenario: Type chips live with the table they scope
- **WHEN** the consumption view renders with defaults
- **THEN** five type chips sit directly above the Consumers table with skill/mcp/cli active and built-ins/shell inactive, and toggling one changes the league only

#### Scenario: Sparkline enlarges in place
- **WHEN** the operator clicks a league row's sparkline
- **THEN** a full-width row opens beneath it showing the same 14 days as a bar chart with readable dated x and integer y axes; a second click closes it and other rows are unaffected

### Requirement: Global filter bar
One filter bar SHALL govern every panel on the consumption tab: time presets (today, yesterday, this week, last week, this month, 30d) plus a custom range, and a project multi-select. All bucketing SHALL use local time.

#### Scenario: Filters compose
- **WHEN** "last week" and two of five projects are selected
- **THEN** the strip, daily chart, and league table all reflect exactly that window and those projects

#### Scenario: Local-time day boundaries
- **WHEN** a session ran 23:30–00:30 local time
- **THEN** its tokens split across the two local days, never bucketed by UTC

### Requirement: At-a-glance strip with context
The strip SHALL show, for the active filters: total tokens with a delta vs the previous window of equal length and the fresh-work share (input + output) named beneath it; an approximate cost at public list price per token — computed only over models with a known list price, never guessed: when coverage is partial the card states the priced share of token volume instead of a delta, and the operator may supply prices for unpriced models via `prices` in `~/.ccwhere/overrides.json` (which the UI's own writes must preserve); session count with the same comparison; top consumer (the Session-lens leader, marked if the Message lens agrees); cache hit rate — `cache_read / (input + cache_read + cache_create)` — rendered as a bullet graph against the 70% target. No number SHALL appear without its comparison (Few pitfall 2).

#### Scenario: Comparison window matches length
- **WHEN** the filter is a 7-day window
- **THEN** deltas compare against the immediately preceding 7 days

### Requirement: Daily chart with drill-down to evidence
The tab SHALL render the daily token components as small multiples (operator pick 2026-07-09): two stacked-bar panels sharing the x axis and drill clicks — "context re-read" (cache read, cache create) and "fresh work" (input, output) — each at its own y scale, because cache read is ~99% of the combined stack and a shared scale renders fresh work sub-pixel. Validated palette, vendored Chart.js, one-time render animation. Legend items toggle their component within its panel. Legend items SHALL toggle their component's visibility (dimmed when hidden) — cache read dominates the stack (~99% on the reference data), so input and output are honest but sub-pixel until the large series are hidden; the default remains the full stack. Clicking a day SHALL show that day's hourly bars; clicking an hour SHALL show the event list — sessions/consumers active in that hour with project, consumer, tokens, and duration — with breadcrumb navigation back up. The drill floor is the event list, never finer bars.

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

### Requirement: By-model breakdown
The consumption view SHALL show a per-model table over the active filters — messages, component tokens grouped under fresh work (input/output) and context re-read (cache read/cache create) header bands, total with a shared-scale bar, and the approximate list-price cost — placed between the daily chart and the league. The table SHALL follow the chart drill: a clicked day or hour scopes the rows and names the scope in the table's kicker; closing the drill restores the window view. Models without a known list price show a muted "—", never a fabricated cost; messages carrying no model are grouped as "(unknown)"; model identifiers render escaped (a model literally named `<synthetic>` exists in real data).

#### Scenario: Unpriced model stays honest
- **WHEN** the operator's history includes a model with no public list price
- **THEN** its row shows tokens in full and "—" for cost, and the strip's coverage figure reflects the unpriced share
