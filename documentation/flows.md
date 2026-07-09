# Flows

The permission-relevant journeys. There is no auth (see `permissions.md`); "protected" here means "capable of side effects or of reading beyond the request".

## 1. Startup (`ccwhere` / `python -m ccwhere`)

1. Bind 127.0.0.1:port **first** — fail fast on conflict, before any work.
2. Full or incremental sync of `~/.claude/projects` into the cache.
3. Open browser (unless `--no-browser`), serve until Ctrl-C (ADR-0001: no daemon).

Side effects: creates/updates `~/.ccwhere/ccwhere.db`. On schema-version mismatch, **deletes** the db files and rebuilds from source (~1s) — by design, announced in `db.py`.

## 2. Sync (`POST /api/sync`)

Operator-triggered (manual refresh default). Global lock serializes concurrent syncs. Re-parses only files whose mtime/size changed. Side effects: cache writes only. Malformed lines are counted, never fatal; unknown event types feed the drift canary rather than erroring.

## 3. Overrides (`POST /api/overrides`)

The **only** endpoint that writes outside the cache: `{"consumer", "demoted"}` updates `~/.ccwhere/overrides.json`. Applies at query time only — the store keeps provenance truth. Malformed body → 400, no partial writes.

## 4. Read API (`GET /api/*`)

health, summary, consumption (+hours/events), ledger, performance, live — all read-only. Every response carries `Cache-Control: no-store`: a stale dashboard is a silent lie.

Trust-boundary notes:

- `/api/ledger` reads project paths recorded in session history (cwd) and itemizes files found there — read-only, sizes only, no content leaves the machine.
- `/api/live` reads the process table (`ps` + `lsof` cwd). Any failure degrades to omitting the data — never an error, never a guess.

## 5. Static serving

Path resolution is confined to the packaged `ui/` directory (resolved-prefix traversal guard); anything outside 404s. Same `no-store` policy — a UI upgrade must never fight browser cache.
