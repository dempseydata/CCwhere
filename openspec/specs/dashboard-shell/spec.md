# dashboard-shell

## Purpose
The application shell: tabs, operator-triggered sync, drift canary, and the manual-refresh-first model.

## Requirements

### Requirement: Shell frame per design system
The dashboard SHALL render the house design system shell (the author's shared design standard v1.2, docs mode, adopted 2026-07-11): neutral light surfaces on white cards, header with wordmark, four-tab underline nav (Consumption, Context ledger, Performance, Live — placeholder bodies allowed until each tab's change lands), sans-serif headlines and labels with mono reserved for data (numbers, paths, code), pill-shaped primary button and filter chips, squared badges, and a blue positive accent rationed to confirmation moments only (healthy canary dot, live running dot, bullet-graph target, agreement flag) — semantic states pair red with blue, never green (Few's colorblind-safe pairing, operator decision 2026-07-11), and never touch data ink; the chart categorical palette stays dataviz-validated, independent of brand. Font stacks fall back to system faces; nothing is fetched. No CDN assets; Chart.js v4 is vendored and loadable. The Inventory tab was retired 2026-07-08: its story is delivered by the Context ledger's drill (operator decision — a dedicated tab would re-present the same data).

#### Scenario: Shell renders offline with tokens applied
- **WHEN** the dashboard loads
- **THEN** the header, four-tab nav, and tokens render per DESIGN.md and `window.Chart` is defined from the vendored file

### Requirement: Manual refresh is the primary control
The header SHALL show a Refresh button that POSTs `/api/sync` and re-renders, plus a last-sync age ("synced N min ago") that updates after refresh. An auto-refresh toggle (30s) SHALL exist, default off, and persist its state locally.

#### Scenario: Operator-controlled freshness
- **WHEN** the operator clicks Refresh
- **THEN** a sync runs, the last-sync age resets, and no timer starts unless the auto-refresh toggle is on

### Requirement: Drift canary indicator
The header SHALL show the canary state from `/api/health`: quiet ("all events recognized") when the latest sync's unknown-type share is ≤1%, firing (red text: "N% of events unrecognized — ccwhere update likely required") when above. The indicator SHALL never be absent.

#### Scenario: Quiet on a healthy machine
- **WHEN** the latest sync reports 0.1% unknown types
- **THEN** the indicator shows the quiet state

#### Scenario: Fires on drift
- **WHEN** a sync reports 4% unknown types
- **THEN** the indicator turns red and names the percentage
