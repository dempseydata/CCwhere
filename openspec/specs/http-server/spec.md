# http-server

## Purpose
Serve the dashboard UI and its JSON API on localhost, read-only against the store, never stale.

## Requirements

### Requirement: On-demand lifecycle
Running `ccwhere` SHALL perform an incremental sync, start serving on localhost, and open the default browser at the dashboard URL. Ctrl-C SHALL stop the process cleanly (no orphaned threads, database connections closed). No launchd/service files SHALL be created (ADR-0001).

#### Scenario: One command to dashboard
- **WHEN** `ccwhere` runs on a machine with existing history
- **THEN** a sync completes first, the server binds, and the browser opens to the dashboard within seconds

#### Scenario: Clean shutdown
- **WHEN** the operator presses Ctrl-C
- **THEN** the process exits promptly with exit code 0 and no background threads survive

### Requirement: Localhost-only binding with explicit port handling
The server SHALL bind to 127.0.0.1 only, default port 8917, overridable via `--port`. If the port is occupied, the process SHALL print a clear error naming the port and exit non-zero — never auto-increment.

#### Scenario: Port conflict is loud
- **WHEN** port 8917 is already bound and `ccwhere` starts
- **THEN** it exits non-zero with a message naming 8917 and suggesting `--port`

#### Scenario: Never exposed beyond the machine
- **WHEN** the server is running
- **THEN** connections to the machine's LAN address on the same port are refused

### Requirement: JSON API for the shell
The server SHALL expose `GET /api/health` (last-sync age in seconds, drift share %, store row counts), `GET /api/summary` (sessions, projects, events, date range of history), and `POST /api/sync` (runs an incremental sync, returns its summary). API responses SHALL be JSON with correct content-type; unknown `/api/*` paths return 404 JSON.

#### Scenario: Refresh round-trip
- **WHEN** the UI POSTs `/api/sync`
- **THEN** the response carries the sync summary (files parsed, events added, drift counts) and a subsequent `/api/health` shows last-sync age near zero

### Requirement: Static UI serving
The server SHALL serve the bundled `ui/` directory (index, JS, CSS, vendored Chart.js) at `/`, with no external network requests required by any page.

#### Scenario: Fully offline dashboard
- **WHEN** the dashboard loads with networking limited to localhost
- **THEN** all assets resolve locally and the shell renders completely

### Requirement: Consumer overrides endpoint
The server SHALL expose `POST /api/overrides` accepting `{"consumer": <name>, "demoted": true|false}`, updating the persistent overrides file, and SHALL include the current demoted list in the `/api/consumption` payload so the UI can render and edit it. Responses carry `Cache-Control: no-store` like all API responses.

#### Scenario: Demote round-trip
- **WHEN** the UI posts `{"consumer": "npm", "demoted": true}` and refetches consumption
- **THEN** the payload's demoted list contains npm and the league treats npm as type shell

### Requirement: Performance endpoint
The server SHALL expose `GET /api/performance` returning the per-tool latency/error aggregation for the standard filter parameters (from, to, projects, types), with `Cache-Control: no-store` like all API responses.

#### Scenario: Filtered aggregation round-trip
- **WHEN** the UI requests `/api/performance?projects=X`
- **THEN** the rows aggregate only project X's tool calls

### Requirement: Live endpoint
The server SHALL expose `GET /api/live` returning live sessions per the liveness rule (5-minute mtime window, request-time disk scan, no store involvement), with `Cache-Control: no-store`.

#### Scenario: Live round-trip
- **WHEN** the UI requests `/api/live` while a session file changed 30 seconds ago
- **THEN** the payload contains that session with a last-activity age of roughly 30 seconds
