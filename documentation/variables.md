# Variables & configuration

## Secrets

None. No API keys, no tokens, no credentials of any kind exist in this system — nothing to rotate, nothing to leak. The tool reads local files the operator already owns and calls no external service.

## Configuration surface

| Item | Where | Default | Risk notes |
| --- | --- | --- | --- |
| `--port` | CLI flag | 8917 | loopback-only regardless of value; conflict fails fast at startup |
| `--no-browser` | CLI flag | off | convenience only |
| `~/.ccwhere/overrides.json` | operator file, UI-managed (demotions) / hand-edited (prices) | absent | `demoted`: cli consumers moved out of the default league; `prices`: per-MTok list prices for models ccwhere does not know (`{"claude-x": {"in":..,"out":..,"cr":..,"cw":..}}`) — UI writes preserve hand-added keys; corrupt/missing → empty, never an error |

## Fixed constants (code, not config — change = code review)

| Constant | Value | Meaning |
| --- | --- | --- |
| `SCHEMA_VERSION` (`db.py`) | string | bump = cache delete + rebuild; the only "migration" mechanism |
| `CANARY_THRESHOLD_PCT` (`server.py`) | 1.0 | drift share above which the canary fires |
| `PAIR_CAP_MS` (`ingest.py`) | 10 min | tool-call pairing cap; beyond it a call is an orphan (NULL duration) |
| `LIVE_WINDOW_S` / `RECENT_WINDOW_S` (`live.py`) | 5 / 15 min | liveness bands |
| `TAIL_BYTES` (`live.py`) | 64 KB | bounded tail read for live activity |

These are constants, not knobs, on purpose: each encodes an operator decision recorded in `openspec/specs/`, and a config file for values nobody varies would be surface without benefit.

## Paths

| Path | Direction | Contents |
| --- | --- | --- |
| `~/.claude/projects/**/*.jsonl` | read | Claude Code session history (source of truth) |
| `~/.claude/plugins/installed_plugins.json` | read | active plugin versions for the ledger scan |
| `~/.ccwhere/ccwhere.db` (+wal/shm) | write | disposable cache — safe to delete at any time |
| `~/.ccwhere/overrides.json` | write | operator curation — survives cache rebuilds |
