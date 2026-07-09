# live-view

## Purpose
Show what is running right now — read-only, from disk truth, independent of sync. The one live element kept when orchestration was cut from scope.

## Requirements

### Requirement: Liveness from disk truth, in two bands
A session SHALL be considered **running now** when its JSONL file's mtime is within the last 5 minutes at request time, and **recently active** when within 5–15 minutes — determined by a direct filesystem scan, never by store contents or sync recency. The two bands render as separate sections. Only in-window files are tailed (bounded read from the end) to extract the latest event: model, event type, and last tool where present. Subagent files SHALL roll up to their parent session. The scan is read-only and per-request. Files older than 15 minutes are history, not live — an open window that is not conversing writes nothing and is indistinguishable from a closed one by files; that gap is covered by the open-windows count, not by guessing.

#### Scenario: Liveness independent of sync
- **WHEN** a session wrote events 1 minute ago but the operator last synced an hour ago
- **THEN** the running-now section shows that session

#### Scenario: Recently active band
- **WHEN** a session last wrote 8 minutes ago
- **THEN** it appears under recently active, visibly distinct from running sessions

#### Scenario: Quiet machine is explicit
- **WHEN** no session file changed within 15 minutes
- **THEN** the view states that nothing is running, never renders blank

### Requirement: Open windows from the process table
The view SHALL show a per-directory count of open Claude Code processes (read-only `ps` + `lsof` cwd lookup), answering "open but idle" — the state file mtimes cannot see. A process cannot be matched to a specific session file, so the count is per working directory, honestly coarse, with a hover explanation. Process inspection failing for any reason SHALL degrade to omitting the strip — never an error, never a guess.

#### Scenario: Idle window still counted
- **WHEN** two Claude Code windows are open on one project but only one is conversing
- **THEN** the open-windows strip shows that directory with count 2 while running-now lists only the conversing session

### Requirement: Read-only live list
The tab SHALL render one row per live session — project, session id, model, relative last-activity time (self-describing staleness), and the latest action in plain words — with **no interaction affordances**: no kill, pause, open, or navigate controls. Read-only is a scope constitution decision (operator, definition phase), not a v1 shortcut.

#### Scenario: No affordances exist
- **WHEN** the live view renders active sessions
- **THEN** no element offers any action on a session

#### Scenario: Self-observation
- **WHEN** a Claude Code session is actively building while the dashboard is open
- **THEN** that session appears with its recent activity described
