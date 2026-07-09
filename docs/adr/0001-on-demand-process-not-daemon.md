# 0001 — On-demand process, not a persistent daemon

Date: 2026-07-08
Status: accepted

## Context

An observability tool is conventionally a daemon: always listening, always
current. The original inspiration (the "command centre" build prompt) runs two
launchd services. OTEL ingest genuinely benefits from an always-on listener,
because Claude Code never retries OTLP posts — events fired while nothing
listens are lost.

Against that: kill-test #3 (red-team.md) flagged the risk that ccwhere is a
periodic audit, not a daily-watch tool; the operator chose manual refresh over
auto-refresh; JSONL — the source of truth — is replayable at any time, so
nothing in P0 depends on uptime; and every persistent service is one more
thing to install, monitor, and debug, which is the exact failure mode the
product exists to criticize.

## Decision

`ccwhere` is a foreground, on-demand process. Running it syncs the JSONL
history, serves the dashboard on localhost, and opens the browser; Ctrl-C
stops it. No launchd, no service files, no background anything in v1.

OTEL ingest (P1) captures events only while ccwhere is running, and is
documented as lossy enrichment on top of replayable JSONL truth. If Phase 2
proves OTEL valuable enough to want complete capture, an *optional*
`ccwhere serve --background` may be added then — adding a daemon later is
cheap; retiring one users depend on is not.

## Consequences

- Install story stays a one-liner; uninstall is `pipx uninstall`.
- The dashboard's data is as fresh as the last run/refresh — the last-sync
  age indicator (PRD story 8) carries the honesty burden.
- Live view works only while ccwhere is open, which matches how a live view
  is actually used.
- OTEL completeness is explicitly sacrificed in v1.
