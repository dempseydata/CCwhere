# Permissions

## The model: single operator, OS-enforced

There are no roles, no sessions, no tokens, and no authorization matrix — deliberately. The permission model is the operating system's:

- The server binds **127.0.0.1 only**; reachability requires a local process.
- Source data (`~/.claude/projects`) and the cache (`~/.ccwhere`) are the operator's own home-directory files under their OS user's permissions.
- ccwhere runs at the invoking user's privilege and never elevates.

Adding an auth layer to a loopback-only, single-user, read-mostly tool would be surface area without a threat it addresses. The honest risk statement is the inverse: **anything running as your OS user can already read your Claude Code history directly** — ccwhere adds one localhost port to that existing reality, exposing aggregates of data the user already owns.

## Operation × surface

| Operation | Surface | Writes | Guard |
| --- | --- | --- | --- |
| View any tab / API | `GET /api/*`, static | none | loopback bind; traversal guard on static paths |
| Trigger sync | `POST /api/sync` | cache only | global lock; per-line fault tolerance |
| Demote/restore consumer | `POST /api/overrides` | `overrides.json` | body validation → 400; cli consumers only (query-time effect) |

## What would change this model

Any of: binding beyond loopback, a remote-access feature, or multi-user use. Each would demand real auth before shipping — treat this file as the tripwire.
