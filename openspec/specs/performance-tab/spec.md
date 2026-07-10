# performance-tab

## Purpose
Show which tools and MCP servers are slow or failing: per-tool latency percentiles and error rates from tool_use → tool_result pairing.

## Requirements

### Requirement: Per-tool latency and error aggregation
The performance view SHALL aggregate tool calls at the finest honest grain per consumer type — MCP rows as `server · tool`, built-ins/cli/skills by their own name; command rows excluded (no tool_result exists by design). Per row: total calls, error count and rate (over all calls), and p50/p95/max latency computed over paired durations only — orphans (NULL duration) count as calls but never enter percentiles. A row with zero paired durations SHALL show no latency numbers rather than fabricated ones. Aggregation SHALL honour the standard filters (time window, projects, types).

#### Scenario: Orphans excluded from percentiles
- **WHEN** a tool has 12 calls of which 2 are orphans
- **THEN** its percentiles are computed over the 10 paired durations and its calls column shows 12

#### Scenario: MCP tools at tool grain
- **WHEN** the playwright MCP server has navigate and click calls
- **THEN** each appears as its own row, comparable against the playwright CLI row

### Requirement: Performance table UI
The tab SHALL render a sortable table (calls, error rate, p50, p95, max — descending click-sort, league pattern), default-sorted by p95 descending — the "what is slow" question. Rows with fewer than 10 paired durations SHALL carry a visible low-sample badge stating the count in plain language (`only x timed calls`), never be hidden. Error rates SHALL render muted when zero and highlighted when non-zero, with no thresholds or traffic-light colouring. Type tags reuse the established colours. The tab SHALL use the shared filter bar (time presets + project multi-select) with identical behaviour to the consumption tab.

#### Scenario: Slowness sorts first, evidence badged
- **WHEN** the tab renders with defaults
- **THEN** rows order by p95 descending and an 11-call vercel row carries a low-sample badge while remaining fully visible

#### Scenario: Failing tools are visible
- **WHEN** a tool has a non-zero error rate
- **THEN** its rate renders highlighted; zero-error rows stay muted
