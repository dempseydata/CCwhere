"""Consumption queries: both lenses, strip, buckets, drill. Pure functions
over a connection + filters ({'from','to','projects'} — local dates, inclusive).
All bucketing in local time (UTC bucketing breaks evening sessions)."""
from datetime import date as _date, datetime, timedelta

TOK = ("COALESCE(m.input_tokens,0)+COALESCE(m.output_tokens,0)"
       "+COALESCE(m.cache_read_tokens,0)+COALESCE(m.cache_create_tokens,0)")
LOCAL_DAY = "date(datetime({c},'localtime'))"
LOCAL_HOUR = "CAST(strftime('%H', datetime({c},'localtime')) AS INT)"

# kill-test #1 rule: agreement across lenses is the signal
AGREE_TOP = 5      # top-5 on both lenses -> 'agree'
DISAGREE_OUT = 10  # top-5 on one, outside top-10 on the other -> 'disagree'


def _etype(f):
    """Effective consumer type: operator-demoted cli consumers count as
    shell (query-time remap; the store keeps provenance truth)."""
    d = sorted(f.get("demoted") or [])
    if not d:
        return "tc.consumer_type", []
    return (f"(CASE WHEN tc.consumer_type='cli' AND tc.consumer IN "
            f"({','.join('?' * len(d))}) THEN 'shell' "
            f"ELSE tc.consumer_type END)", d)


def _filters(f, ts_col):
    conds, args = [], []
    if f.get("from"):
        conds.append(f"{LOCAL_DAY.format(c=ts_col)} >= ?")
        args.append(f["from"])
    if f.get("to"):
        conds.append(f"{LOCAL_DAY.format(c=ts_col)} <= ?")
        args.append(f["to"])
    if f.get("projects"):
        conds.append(f"s.project IN ({','.join('?' * len(f['projects']))})")
        args.extend(f["projects"])
    # consumer-type scoping applies only to tool_calls-based queries
    if f.get("types") and ts_col.startswith("tc."):
        e, ea = _etype(f)
        conds.append(f"{e} IN ({','.join('?' * len(f['types']))})")
        args.extend(ea + f["types"])
    return " AND ".join(conds) or "1=1", args


def _session_totals(f):
    w, a = _filters(f, "m.ts")
    return (f"SELECT m.session_id sid, SUM({TOK}) total FROM messages m "
            f"JOIN sessions s ON s.session_id=m.session_id WHERE {w} "
            f"GROUP BY m.session_id"), a


def league(conn, f):
    # Default scope: actionable Consumers (installable/uninstallable).
    # Built-ins and shell utilities ride in nearly every session, so the
    # Session lens hands them the whole corpus (spec: on demand only).
    f = dict(f, types=f.get("types") or ["skill", "mcp", "cli"])
    st_sql, st_args = _session_totals(f)
    wt, at = _filters(f, "tc.ts")
    # Session lens: consumer inherits totals of sessions it appeared in
    e, ea = _etype(f)
    lens_a = conn.execute(
        f"WITH st AS ({st_sql}) "
        f"SELECT c.consumer, c.consumer_type, COUNT(*) n, SUM(st.total) v "
        f"FROM (SELECT DISTINCT tc.consumer, {e} consumer_type, tc.session_id "
        f"      FROM tool_calls tc JOIN sessions s ON s.session_id=tc.session_id "
        f"      WHERE {wt}) c "
        f"JOIN st ON st.sid=c.session_id GROUP BY c.consumer, c.consumer_type",
        st_args + ea + at).fetchall()
    # Message lens: only the exact messages that invoked the consumer
    lens_b = dict(conn.execute(
        f"SELECT d.consumer, SUM({TOK}) FROM "
        f"(SELECT DISTINCT tc.consumer, tc.session_id sid, tc.line_no ln "
        f" FROM tool_calls tc JOIN sessions s ON s.session_id=tc.session_id "
        f" WHERE {wt}) d "
        f"JOIN messages m ON m.session_id=d.sid AND m.line_no=d.ln "
        f"GROUP BY d.consumer", at).fetchall())
    spark = _spark(conn, f)

    rows = [{"consumer": c, "type": t, "sessions": n,
             "session_tokens": v or 0, "message_tokens": lens_b.get(c, 0) or 0,
             "spark": spark.get(c, [0] * 14)}
            for c, t, n, v in lens_a]
    rows.sort(key=lambda r: -r["session_tokens"])
    rank_a = {r["consumer"]: i + 1 for i, r in enumerate(rows)}
    by_b = sorted(rows, key=lambda r: -r["message_tokens"])
    rank_b = {r["consumer"]: i + 1 for i, r in enumerate(by_b)}
    for r in rows:
        ra, rb = rank_a[r["consumer"]], rank_b[r["consumer"]]
        if r["sessions"] == 1:
            r["flag"] = "n1"
        elif ra <= AGREE_TOP and rb <= AGREE_TOP:
            r["flag"] = "agree"
        elif (ra <= AGREE_TOP and rb > DISAGREE_OUT) or \
             (rb <= AGREE_TOP and ra > DISAGREE_OUT):
            r["flag"] = "disagree"
        else:
            r["flag"] = ""
    return rows


def _spark(conn, f):
    """Daily invocation counts per consumer, last 14 local days ending 'to'."""
    end = datetime.strptime(f["to"], "%Y-%m-%d").date() if f.get("to") \
        else _date.today()
    days = [(end - timedelta(days=13 - i)).isoformat() for i in range(14)]
    idx = {d: i for i, d in enumerate(days)}
    w, a = _filters(dict(f, **{"from": days[0], "to": days[-1]}), "tc.ts")
    out = {}
    for c, d, n in conn.execute(
            f"SELECT tc.consumer, {LOCAL_DAY.format(c='tc.ts')} d, COUNT(*) "
            f"FROM tool_calls tc JOIN sessions s ON s.session_id=tc.session_id "
            f"WHERE {w} GROUP BY tc.consumer, d", a).fetchall():
        out.setdefault(c, [0] * 14)
        if d in idx:
            out[c][idx[d]] = n
    return out


def _totals(conn, f):
    w, a = _filters(f, "m.ts")
    r = conn.execute(
        f"SELECT COALESCE(SUM(m.input_tokens),0), COALESCE(SUM(m.output_tokens),0),"
        f" COALESCE(SUM(m.cache_read_tokens),0), COALESCE(SUM(m.cache_create_tokens),0),"
        f" COUNT(DISTINCT m.session_id) FROM messages m "
        f"JOIN sessions s ON s.session_id=m.session_id WHERE {w}", a).fetchone()
    return {"input": r[0], "output": r[1], "cache_read": r[2],
            "cache_create": r[3], "sessions": r[4]}


def strip(conn, f):
    cur = _totals(conn, f)
    tokens = sum(cur[k] for k in ("input", "output", "cache_read", "cache_create"))
    prev = {"tokens": None, "sessions": None}
    if f.get("from") and f.get("to"):
        d0 = datetime.strptime(f["from"], "%Y-%m-%d").date()
        d1 = datetime.strptime(f["to"], "%Y-%m-%d").date()
        span = (d1 - d0).days + 1
        pf = dict(f, **{"from": (d0 - timedelta(days=span)).isoformat(),
                        "to": (d0 - timedelta(days=1)).isoformat()})
        p = _totals(conn, pf)
        prev = {"tokens": sum(p[k] for k in
                              ("input", "output", "cache_read", "cache_create")),
                "sessions": p["sessions"]}
    denom = cur["input"] + cur["cache_read"] + cur["cache_create"]
    rate = round(cur["cache_read"] / denom * 100, 1) if denom else None
    top = None
    rows = league(conn, f)
    if rows:
        top = {"consumer": rows[0]["consumer"], "type": rows[0]["type"],
               "agree": rows[0]["flag"] == "agree"}
    return {"tokens": tokens, "tokens_prev": prev["tokens"],
            "sessions": cur["sessions"], "sessions_prev": prev["sessions"],
            "cache_rate_pct": rate, "top": top}


def daily(conn, f):
    w, a = _filters(f, "m.ts")
    day = LOCAL_DAY.format(c="m.ts")
    return [{"date": r[0], "input": r[1], "output": r[2],
             "cache_read": r[3], "cache_create": r[4]}
            for r in conn.execute(
                f"SELECT {day}, COALESCE(SUM(m.input_tokens),0),"
                f" COALESCE(SUM(m.output_tokens),0),"
                f" COALESCE(SUM(m.cache_read_tokens),0),"
                f" COALESCE(SUM(m.cache_create_tokens),0) FROM messages m "
                f"JOIN sessions s ON s.session_id=m.session_id "
                f"WHERE {w} GROUP BY 1 ORDER BY 1", a).fetchall()]


def hours(conn, f, date):
    ff = dict(f, **{"from": date, "to": date})
    w, a = _filters(ff, "m.ts")
    hr = LOCAL_HOUR.format(c="m.ts")
    return [{"hour": r[0], "input": r[1], "output": r[2],
             "cache_read": r[3], "cache_create": r[4]}
            for r in conn.execute(
                f"SELECT {hr}, COALESCE(SUM(m.input_tokens),0),"
                f" COALESCE(SUM(m.output_tokens),0),"
                f" COALESCE(SUM(m.cache_read_tokens),0),"
                f" COALESCE(SUM(m.cache_create_tokens),0) FROM messages m "
                f"JOIN sessions s ON s.session_id=m.session_id "
                f"WHERE {w} GROUP BY 1 ORDER BY 1", a).fetchall()]


def events(conn, f, date, hour):
    """Drill floor: what ran in one local hour, per session x consumer."""
    ff = dict(f, **{"from": date, "to": date})
    w, a = _filters(ff, "tc.ts")
    hcond = f"{LOCAL_HOUR.format(c='tc.ts')} = ?"
    base = (f"FROM tool_calls tc JOIN sessions s ON s.session_id=tc.session_id "
            f"WHERE {w} AND {hcond}")
    args = a + [hour]
    e, ea = _etype(ff)  # display type honours operator demotions
    calls = {(r[0], r[1]): {"session": r[0], "project": r[2], "consumer": r[1],
                            "type": r[3], "calls": r[4], "duration_ms": r[5]}
             for r in conn.execute(
                 f"SELECT tc.session_id, tc.consumer, s.project,"
                 f" {e}, COUNT(*),"
                 f" COALESCE(SUM(tc.duration_ms),0) {base} "
                 f"GROUP BY tc.session_id, tc.consumer", ea + args).fetchall()}
    toks = dict(((r[0], r[1]), r[2]) for r in conn.execute(
        f"SELECT d.sid, d.consumer, SUM({TOK}) FROM "
        f"(SELECT DISTINCT tc.session_id sid, tc.consumer, tc.line_no ln "
        f" {base}) d "
        f"JOIN messages m ON m.session_id=d.sid AND m.line_no=d.ln "
        f"GROUP BY d.sid, d.consumer", args).fetchall())
    rows = list(calls.values())
    for r in rows:
        r["tokens"] = toks.get((r["session"], r["consumer"]), 0) or 0
    rows.sort(key=lambda r: -r["tokens"])
    return rows[:200]


def performance(conn, f):
    """Per-tool latency/errors (story 6). Finest honest grain: MCP rows are
    server · tool; others by name; commands excluded (no tool_result exists).
    Percentiles over paired durations only — orphans count as calls, never
    as measurements. Nearest-rank p95, no interpolation."""
    import statistics
    w, a = _filters(f, "tc.ts")
    e, ea = _etype(f)  # display type honours operator demotions
    groups = {}
    for ctype, consumer, mcp_tool, dur, err in conn.execute(
            f"SELECT {e}, tc.consumer, tc.mcp_tool, tc.duration_ms,"
            f" COALESCE(tc.error, 0)"
            f" FROM tool_calls tc JOIN sessions s ON s.session_id=tc.session_id"
            f" WHERE {w} AND tc.consumer_type != 'command'", ea + a):
        name = f"{consumer} · {mcp_tool}" if ctype == "mcp" and mcp_tool \
            else consumer
        g = groups.setdefault((ctype, name),
                              {"calls": 0, "errors": 0, "durs": []})
        g["calls"] += 1
        g["errors"] += err
        if dur is not None:
            g["durs"].append(dur)
    out = []
    for (ctype, name), g in groups.items():
        d = sorted(g["durs"])
        n = len(d)
        out.append({
            "consumer": name, "type": ctype, "calls": g["calls"],
            "errors": g["errors"],
            "err_rate": round(g["errors"] / g["calls"], 4),
            "n_paired": n,
            "p50": int(statistics.median(d)) if n else None,
            "p95": d[-(-n * 95 // 100) - 1] if n else None,  # nearest-rank
            "max": d[-1] if n else None,
        })
    out.sort(key=lambda r: -(r["p95"] if r["p95"] is not None else -1))
    return out


def ledger_medians(conn):
    """Per-project first-call medians (parent sessions only) + calibrated floor.
    First call = first message with any usage; value = input + cache tokens
    (output excluded: the question is what the session paid to start)."""
    import statistics
    rows = conn.execute(
        "SELECT s.project, s.cwd, m.val FROM sessions s JOIN ("
        " SELECT session_id,"
        "  COALESCE(input_tokens,0)+COALESCE(cache_read_tokens,0)"
        "  +COALESCE(cache_create_tokens,0) val,"
        "  ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY line_no) rn"
        " FROM messages WHERE input_tokens IS NOT NULL"
        "  OR cache_read_tokens IS NOT NULL OR cache_create_tokens IS NOT NULL"
        ") m ON m.session_id = s.session_id AND m.rn = 1 "
        "WHERE s.parent_session IS NULL").fetchall()
    groups = {}
    for project, cwd, val in rows:
        g = groups.setdefault(project, {"vals": [], "cwd": None})
        g["vals"].append(val)
        g["cwd"] = g["cwd"] or cwd
    projects = [{"project": p, "cwd": g["cwd"],
                 "median": int(statistics.median(g["vals"])),
                 "n": len(g["vals"])}
                for p, g in groups.items()]
    projects.sort(key=lambda r: -r["median"])
    eligible = [p["median"] for p in projects if p["n"] >= 3]
    floor = min(eligible) if eligible else (
        min((p["median"] for p in projects), default=0))
    return {"projects": projects, "floor": floor}


def skill_usage(conn):
    """All-time usage per consumer: uses, first/last-used dates, 14-day spark.
    Union of Skill-tool invocations and typed slash commands — skill-backed
    commands are invoked both ways. Keyed by the invocation name (may be bare
    or package-prefixed)."""
    rows = conn.execute(
        "SELECT consumer, COUNT(*), MIN(date(datetime(ts,'localtime'))),"
        " MAX(date(datetime(ts,'localtime'))) "
        "FROM tool_calls WHERE consumer_type IN ('skill','command') "
        "GROUP BY consumer").fetchall()
    spark = _spark(conn, {"types": ["skill", "command"]})
    return {c: {"uses": n, "first": first, "last": last,
                "spark": spark.get(c, [0] * 14)}
            for c, n, first, last in rows}


def match_skill_usage(usage, names, pkg):
    """Invocations arrive bare ('write-prd') or prefixed
    ('pm-execution:write-prd'), under any of the skill's aliases
    (frontmatter name, directory name); prefix must agree when present."""
    names = {n for n in (names if isinstance(names, (set, list, tuple))
                         else [names]) if n}
    total = {"uses": 0, "first": None, "last": None, "spark": [0] * 14}
    for key, u in usage.items():
        prefix, _, base = key.rpartition(":")
        if base not in names or (prefix and pkg and prefix != pkg):
            continue
        total["uses"] += u["uses"]
        total["first"] = min(filter(None, [total["first"], u.get("first")]),
                             default=None)
        total["last"] = max(total["last"] or "", u["last"] or "") or None
        total["spark"] = [a + b for a, b in zip(total["spark"], u["spark"])]
    return total


def project_list(conn):
    """All projects (unfiltered) for the filter bar, busiest first."""
    return [r[0] for r in conn.execute(
        "SELECT project, COUNT(*) n FROM sessions GROUP BY project "
        "ORDER BY n DESC").fetchall()]
