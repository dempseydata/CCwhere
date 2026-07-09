# event-store

## Purpose
Persist parsed session history as atomic, queryable event rows — the disposable cache every view is derived from.

## Requirements

### Requirement: Atomic event storage with query-time aggregation
The store SHALL persist parsed session history as atomic per-event rows in a single SQLite database (`~/.ccwhere/ccwhere.db`, WAL mode) with no pre-aggregated rollup tables. All views (daily/hourly/minute buckets, per-Consumer, per-Project) SHALL be derivable by SQL aggregation at query time. Timestamps SHALL be stored in UTC; local-time bucketing is applied at query time.

#### Scenario: Same rows serve every grain
- **WHEN** the same stored events are queried grouped by day and then by hour
- **THEN** both results come from the identical rows with no separate rollup storage, and hourly totals sum to the daily total

#### Scenario: Local-time day boundaries
- **WHEN** a message timestamped 2026-07-07T23:30:00-04:00 (03:30 UTC next day) is bucketed by day in local time
- **THEN** it lands on 2026-07-07, not 2026-07-08

### Requirement: Message events carry full usage
The store SHALL record one row per assistant/user message event, carrying the session id, project, timestamp, role, model, and the complete usage block (input, output, cache-read, cache-creation tokens) when present. Fields absent from a message SHALL be stored as NULL, never zero-filled.

#### Scenario: Usage preserved verbatim
- **WHEN** an assistant message with `input_tokens: 12, cache_read_input_tokens: 39810` is ingested
- **THEN** a query for that message returns exactly those values, with unpopulated usage fields NULL

### Requirement: Tool call rows with pairing
The store SHALL record one row per tool_use, keyed by `tool_use_id`, with tool name, Consumer classification (skill / MCP server / CLI program / shell utility / command / built-in tool per CONTEXT.md), timestamps, **the source line number of the message that issued it** (exact linkage to that message's usage row for the Message lens), and — once its tool_result is seen — duration and error flag. Command rows (from `<command-name>` tags) have no tool_result and carry NULL duration by design. Durations SHALL be capped at 10 minutes; a tool_use with no result within the cap is stored with NULL duration (orphan), never a fabricated value.

#### Scenario: Pair resolves to duration
- **WHEN** a tool_use at T and its matching tool_result at T+4.2s are ingested
- **THEN** the row shows duration 4200ms and error flag from the result

#### Scenario: Orphan stays honest
- **WHEN** a tool_use never receives a matching result (crashed session)
- **THEN** its duration is NULL and it is excluded from latency percentiles rather than counted as slow

#### Scenario: Tool call links to its exact message
- **WHEN** a tool_use is ingested from line 41 of a session file
- **THEN** its row carries line 41, joining unambiguously to the message row at (session, line 41)

### Requirement: Session rows and sync bookkeeping
The store SHALL keep one row per session (id, project, source file, parent subagent linkage if any, first/last event timestamps, and the session's working directory (cwd) as first seen in its events) and per-file sync state (path, mtime, size, last-synced) sufficient for incremental re-sync to skip unchanged files. Sessions whose events carry no cwd SHALL store NULL, never a guessed path.

#### Scenario: Unchanged file skipped
- **WHEN** a sync runs and a session file's mtime and size match its sync state
- **THEN** the file is not re-parsed

#### Scenario: Real path captured
- **WHEN** a session's events include `cwd: /Users/me/code/demo`
- **THEN** its session row carries that path, enabling honest labels and the ledger's static scan

### Requirement: Drift counters are stored
The store SHALL persist per-sync counts of unrecognized event types and unrecognized fields (the drift canary's data), queryable as a share of total events.

#### Scenario: Canary share computable
- **WHEN** a sync parses 10,000 events of which 300 had unknown types
- **THEN** a query returns a 3% unrecognized share for that sync

### Requirement: The store is a disposable cache
The database SHALL be treated as a cache of the JSONL truth: a schema-version value is stored, and on mismatch with the running code the store SHALL be deleted and rebuilt by full backfill automatically. No in-place schema migrations SHALL exist in v1.

#### Scenario: Upgrade rebuilds silently
- **WHEN** ccwhere starts against a store written by an older schema version
- **THEN** the store is rebuilt from JSONL (measured ~1.3s on the reference machine) and the dashboard serves current-schema data
