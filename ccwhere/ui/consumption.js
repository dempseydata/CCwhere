/* Consumption tab: filter bar, strip, daily chart, league table, drill-down. */
"use strict";

(function () {
  const css = (v) => getComputedStyle(document.documentElement)
    .getPropertyValue(v).trim();
  const COMPONENTS = [
    ["cache_read", "re-read", "--cat-cache-read"],
    ["input", "input", "--cat-input"],
    ["output", "output", "--cat-output"],
    ["cache_create", "saved for re-use", "--cat-cache-create"],
  ];
  const LENS_A_TIP = "Counts every token of every session this consumer " +
    "appeared in. Reads HIGH — one long session inflates everything it " +
    "touched.";
  const LENS_B_TIP = "Counts only the messages that directly used this " +
    "consumer (a message can credit several). Reads LOW — the effect of a " +
    "call lands after the call.";
  const FLAG_TIPS = {
    agree: "Ranks high on BOTH counts — the finding is robust. Safe to act on.",
    disagree: "High on one count, low on the other — usually one long " +
      "session inflating it, not a real burner. Check its sessions first.",
    n1: "Seen in one session only — a single observation, no basis for a ranking.",
  };

  const state = { preset: "30d", from: null, to: null,
                  types: { skill: true, mcp: true, cli: true,
                           builtin: false, shell: false },
                  fresh: false,
                  demoted: new Set(), hidden: new Set(),
                  projects: new Set(), drill: null, animated: false,
                  sortKey: "message_tokens" };  // default: direct message tokens
  let charts = [];

  const { PRESETS, chipCSS, projLabel, tagCSS, bindTips, fmtTok } = window.ccw;
  const presetRange = (p) => window.ccw.presetRange(p, [state.from, state.to]);

  function delta(cur, prev) {
    if (prev == null || prev === 0) return "";
    const pct = Math.round((cur - prev) / prev * 100);
    // a tiny base makes percentages absurd; show the absolute instead
    if (Math.abs(pct) > 999) return `vs ${fmtTok(prev)} previous`;
    return `${pct >= 0 ? "+" : ""}${pct}% vs previous`;
  }
  function sparkSVG(arr) {
    const mx = Math.max(...arr, 1);
    const bars = arr.map((v, i) =>
      v ? `<rect x="${i * 5}" y="${16 - v / mx * 13}" width="4" ` +
          `height="${(v / mx * 13 + 2).toFixed(1)}" fill="#5a5a5c" rx="1"/>`
        : `<rect x="${i * 5}" y="14.5" width="4" height="1.5" fill="#e5e5e5"/>`
    ).join("");
    return `<svg width="70" height="17" viewBox="0 0 70 17">${bars}</svg>`;
  }
  function bulletSVG(pct) {
    if (pct == null) return "—";
    const w = 180, x = (v) => v / 100 * w;
    return `<svg width="${w + 58}" height="24">
      <rect x="0" y="6" width="${x(60)}" height="12" fill="#ececec"/>
      <rect x="${x(60)}" y="6" width="${x(20)}" height="12" fill="#f2f2f2"/>
      <rect x="${x(80)}" y="6" width="${x(20)}" height="12" fill="#f7f7f7"/>
      <rect x="0" y="9" width="${x(Math.min(pct, 100))}" height="6" fill="#0a0a0a"/>
      <rect x="${x(70)}" y="3" width="2.5" height="18" fill="#3772cf"/>
      <text x="${w + 8}" y="17" font-family="ui-monospace,Menlo" font-size="12"
        fill="#1c1c1e">${pct}%</text></svg>`;
  }

  function render(el) {
    el.innerHTML = `
      <div id="cFiltersTime" style="display:flex;align-items:center;gap:8px;
        flex-wrap:wrap;margin-bottom:10px"></div>
      <div id="cFiltersProj" style="display:flex;align-items:center;gap:8px;
        flex-wrap:wrap;margin-bottom:20px"></div>
      <div class="strip" id="cStrip"></div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;
        margin:28px 0 6px">
        <div><div class="kicker">Where tokens flow</div>
        <h1 id="cTitle">Daily consumption</h1></div>
        <div style="text-align:right">
          <div id="cCrumb" style="font-family:var(--mono);font-size:11.5px;
            color:var(--muted)"></div>
          <div id="cLegend" style="display:flex;gap:16px;justify-content:flex-end;
            font-family:var(--mono);font-size:11px;color:var(--sec);
            margin-top:6px"></div>
        </div>
      </div>
      <div id="cPlot"><canvas id="cChart" height="90"></canvas></div>
      <div id="cModels" style="margin-top:28px"></div>
      <div id="cLeagueWrap" style="margin-top:30px">
        <div class="kicker">League table · ranked by direct message tokens,
        and whole session tokens</div>
        <h1 style="margin-bottom:8px">Consumers</h1>
        <div id="cTypes" style="display:flex;align-items:center;gap:8px;
          flex-wrap:wrap;margin-bottom:12px"></div>
        <div id="cLeague"></div>
      </div>`;
    renderFilters(el);
    renderTypes(el);
    load(el);
  }

  const TYPE_CHIPS = [
    ["skill", "skills", null],
    ["mcp", "MCP servers", null],
    ["cli", "CLI programs", null],
    ["builtin", "built-ins", "Claude Code's own tools (Read, Bash, Edit…) " +
      "appear in nearly every session, so whole-session counting hands " +
      "them everything and they drown the ranking. Nothing to prune " +
      "anyway."],
    ["shell", "shell utilities", "Commands that ship with the operating " +
      "system (grep, ls, sed…) — detected by where the program lives, not " +
      "a curated list. In every session and not yours to uninstall, so " +
      "off by default. Includes anything you move out yourself."],
  ];

  function renderTypes(el) {
    const box = el.querySelector("#cTypes");
    box.innerHTML = `<span style="font-size:12px;color:var(--muted)">types</span>` +
      TYPE_CHIPS.map(([k, label, tip]) =>
        `<span data-type="${k}"${tip ? ` data-tip="${tip}"` : ""}
          style="${chipCSS(state.types[k])}">${label}</span>`).join("") +
      `<span style="width:1px;height:18px;background:var(--border);
        margin:0 8px"></span>
      <span style="font-size:12px;color:var(--muted)">counting</span>
      <span id="cFresh" data-tip="Count only input + output — the new work a
        consumer caused — instead of the full context of its invoking
        messages. Re-ranks both columns; agreement flags recompute.
        Experimental: being evaluated, may not stay."
        style="${chipCSS(state.fresh)}">fresh work only</span>`;
    box.querySelector("#cFresh").addEventListener("click", () => {
      state.fresh = !state.fresh;
      renderTypes(el); load(el);
    });
    box.querySelectorAll("[data-type]").forEach((c) =>
      c.addEventListener("click", () => {
        state.types[c.dataset.type] = !state.types[c.dataset.type];
        renderTypes(el); load(el);
      }));
    bindTips(box);
  }

  let projectIds = [];

  function renderFilters(el) {
    const bar = el.querySelector("#cFiltersTime");
    const projBar = el.querySelector("#cFiltersProj");
    bar.innerHTML = PRESETS.map(([k, label]) =>
      `<span data-preset="${k}" style="${chipCSS(state.preset === k)}">${label}</span>`
    ).join("") +
      (state.preset === "custom"
        ? ` <input type="date" id="cFrom" value="${state.from || ""}">
            <input type="date" id="cTo" value="${state.to || ""}">` : "");
    projBar.innerHTML =
      projectIds.map((p) =>
        `<span data-proj="${p}" style="${chipCSS(state.projects.has(p))}">` +
        `${projLabel(p, projectIds)}</span>`).join("");
    bindTips(projBar);
    projBar.querySelectorAll("[data-proj]").forEach((c) =>
      c.addEventListener("click", () => {
        const p = c.dataset.proj;
        state.projects.has(p) ? state.projects.delete(p) : state.projects.add(p);
        state.drill = null; renderFilters(el); load(el);
      }));
    bar.querySelectorAll("[data-preset]").forEach((c) =>
      c.addEventListener("click", () => {
        state.preset = c.dataset.preset; state.drill = null;
        renderFilters(el);
        if (state.preset !== "custom" || (state.from && state.to)) load(el);
      }));
    ["cFrom", "cTo"].forEach((id) => {
      const i = bar.querySelector("#" + id);
      if (i) i.addEventListener("change", () => {
        state.from = bar.querySelector("#cFrom").value || null;
        state.to = bar.querySelector("#cTo").value || null;
        if (state.from && state.to) load(el);
      });
    });
  }

  function qs() {
    const [from, to] = presetRange(state.preset);
    const p = new URLSearchParams();
    if (from) p.set("from", from);
    if (to) p.set("to", to);
    if (state.projects.size) p.set("projects", [...state.projects].join(","));
    const on = Object.keys(state.types).filter((t) => state.types[t]);
    // "__none__" matches nothing: an all-off selection means an empty league,
    // not a silent fall back to the server default
    p.set("types", on.length ? on.join(",") : "__none__");
    if (state.fresh) p.set("fresh", "1");
    return p.toString();
  }

  async function load(el) {
    const r = await fetch("/api/consumption?" + qs(), {cache: "no-store"});
    const data = await r.json();
    state.demoted = new Set(data.demoted || []);
    if (!projectIds.length && data.projects) {
      projectIds = data.projects; renderFilters(el);
    }
    renderStrip(el, data.strip, data.cost);
    state.daily = data.daily;
    state.windowModels = data.models;
    state.windowCost = data.cost;
    renderDrill(el);
    refreshModels(el);
    renderLeague(el, data.league);
  }

  const fmtUsd = (v) => v == null ? "—"
    : "$" + (v >= 1000 ? Math.round(v).toLocaleString() : v.toFixed(2));

  function renderStrip(el, s, cost) {
    const cov = cost && cost.coverage_pct;
    el.querySelector("#cStrip").innerHTML = `
      <div><div class="label">Tokens</div>
        <div class="stat">${fmtTok(s.tokens)}</div>
        <div class="delta">${fmtTok(s.fresh)} fresh work${
          delta(s.tokens, s.tokens_prev)
            ? " · " + delta(s.tokens, s.tokens_prev) : ""}</div></div>
      <div><div class="label"><span data-tip="What this window would cost at
          public list price per token. Models with no public list price are
          excluded, never guessed — coverage says how much of the token
          volume is priced. Add prices for other models under 'prices' in
          ~/.ccwhere/overrides.json." style="border-bottom:1px dotted
          var(--muted);cursor:help">≈ Cost · list price</span></div>
        <div class="stat">${fmtUsd(cost && cost.usd)}</div>
        <div class="delta">${cov != null && cov < 100
          ? `covers ${cov}% of tokens`
          : delta(cost && cost.usd, cost && cost.usd_prev) || "&nbsp;"}</div></div>
      <div><div class="label">Sessions</div>
        <div class="stat">${s.sessions}</div>
        <div class="delta">${delta(s.sessions, s.sessions_prev) || "&nbsp;"}</div></div>
      <div><div class="label">Top consumer</div>
        <div class="stat" style="font-size:15px;line-height:2.1">
          ${s.top ? s.top.consumer : "—"}
          <small>${s.top ? s.top.type : ""}</small></div>
        <div class="delta">${s.top && s.top.agree ? "top on both counts" : ""}</div></div>
      <div><div class="label" data-tip="How much of the context Claude re-read
          from cache instead of paying full price to resend. Higher is
          cheaper." style="border-bottom:1px dotted var(--muted);
          cursor:help;display:inline-block">Context re-used · target 70%</div>
        <div style="margin-top:8px">${bulletSVG(s.cache_rate_pct)}</div></div>`;
    bindTips(el.querySelector("#cStrip"));
  }

  async function refreshModels(el) {
    // the by-model table follows the chart drill; closing restores the
    // window view from the cached main payload
    if (!state.drill) {
      renderModels(el, state.windowModels, state.windowCost, "");
      return;
    }
    const p = new URLSearchParams(qs());
    p.set("date", state.drill.date);
    if (state.drill.hour != null) p.set("hour", state.drill.hour);
    const r = await (await fetch("/api/consumption/models?" + p,
                                 {cache: "no-store"})).json();
    const scope = state.drill.hour != null
      ? `${state.drill.date} · ${String(state.drill.hour).padStart(2, "0")}:00`
      : state.drill.date;
    renderModels(el, r.models, r.cost, scope);
  }

  function renderModels(el, models, cost, scope) {
    const box = el.querySelector("#cModels");
    if (!models || !models.length) { box.innerHTML = ""; return; }
    const tot = (r) => r.input + r.output + r.cache_read + r.cache_create;
    const maxT = Math.max(...models.map(tot), 1);
    const cov = cost && cost.coverage_pct;
    const num = (v) => `<td class="num" style="text-align:right;font-size:12px;
      border-bottom:1px solid var(--row)">${fmtTok(v)}</td>`;
    box.innerHTML = `
      <div class="kicker" style="margin-bottom:6px">By model${scope
        ? ` · ${scope}` : ""} · ≈ cost at
        public list price${cov != null && cov < 100 ? ` · priced coverage
        ${cov}% — unpriced models show —` : ""}</div>
      <table style="width:100%;border-collapse:collapse"><thead>
      <tr>${[["", 3], ["fresh work", 2], ["context re-read", 2], ["", 2]]
        .map(([g, span]) => `<th colspan="${span}" style="text-align:center;
          font-family:var(--sans);font-size:10px;font-weight:600;letter-spacing:.06em;
          text-transform:uppercase;color:var(--sec);font-weight:600;
          ${g ? "border-bottom:1px solid var(--border)" : ""};
          padding:0 8px 3px">${g}</th>`).join("")}</tr>
      <tr>
        ${["model", "", "messages", "input", "output", "re-read",
           "saved", "total", "≈ cost"].map((h, i) =>
          `<th style="text-align:${i < 2 ? "left" : "right"};
            font-family:var(--sans);font-size:11px;letter-spacing:.05em;
            text-transform:uppercase;color:var(--sec);font-weight:600;
            padding:4px 0 6px;border-bottom:1px solid var(--border)">${h}</th>`
        ).join("")}</tr></thead>
      <tbody>${models.map((r) => `<tr>
        <td class="num" style="padding:8px 12px 8px 0;font-size:12.5px;
          border-bottom:1px solid var(--row)">${r.model
            .replace(/&/g, "&amp;").replace(/</g, "&lt;")}</td>
        <td style="border-bottom:1px solid var(--row);width:130px">
          <div style="height:6px;border-radius:2px;background:var(--ink);
            opacity:.75;width:${Math.max(tot(r) / maxT * 110, 2).toFixed(0)}px">
          </div></td>
        <td class="num" style="text-align:right;font-size:12px;
          border-bottom:1px solid var(--row)">${r.messages}</td>
        ${num(r.input)}${num(r.output)}${num(r.cache_read)}${num(r.cache_create)}
        <td class="num" style="text-align:right;font-size:12px;font-weight:600;
          border-bottom:1px solid var(--row)">${fmtTok(tot(r))}</td>
        <td class="num" style="text-align:right;font-size:12px;
          ${r.usd == null ? "color:var(--muted)" : ""};
          border-bottom:1px solid var(--row)">${fmtUsd(r.usd)}</td>
      </tr>`).join("")}</tbody></table>`;
  }

  function renderDrill(el) {
    const crumb = el.querySelector("#cCrumb");
    const title = el.querySelector("#cTitle");
    const plot = el.querySelector("#cPlot");
    if (!state.drill) {
      title.textContent = "Daily consumption";
      crumb.innerHTML = "click a day for hours, an hour for events";
      plot.innerHTML = `<div id="cCharts"></div>`;
      drawChart(plot.querySelector("#cCharts"), state.daily.map((d) => d.date),
                state.daily, (i) => {
                  state.drill = { date: state.daily[i].date };
                  renderDrill(el);
                  refreshModels(el);
                });
    } else {
      // Day view: hourly chart stays put; hour details open beneath it.
      const d = state.drill.date;
      const hour = state.drill.hour;
      title.textContent = d;
      crumb.innerHTML = `<a href="#" id="cBack">← all days</a>` +
        (hour == null ? ` · click an hour` : ``);
      fetch(`/api/consumption/hours?date=${d}&` + qs(), {cache: "no-store"}).then((r) => r.json())
        .then((hrs) => {
          plot.innerHTML = `<div id="cCharts"></div>
            <div id="cDetails"></div>`;
          const sel = hour == null ? -1 : hrs.findIndex((h) => h.hour === hour);
          drawChart(plot.querySelector("#cCharts"),
                    hrs.map((h) => `${String(h.hour).padStart(2, "0")}:00`),
                    hrs, (i) => {
                      state.drill = { date: d, hour: hrs[i].hour };
                      renderDrill(el);
                      refreshModels(el);
                    }, sel);
          if (hour != null) renderDetails(el, d, hour);
        });
      crumbNav(el);
    }
  }

  function renderDetails(el, date, hour) {
    const box = el.querySelector("#cDetails");
    const label = `${String(hour).padStart(2, "0")}:00–` +
      `${String((hour + 1) % 24).padStart(2, "0")}:00`;
    box.innerHTML = `
      <div style="border:1.5px solid var(--panel-border);border-radius:8px;
        padding:16px 20px;margin-top:16px;background:var(--card)">
        <div style="display:flex;justify-content:space-between;
          align-items:baseline;margin-bottom:10px">
          <span class="kicker">Drill-down · ${date} · ${label}</span>
          <a href="#" id="cCloseDetails" style="font-family:var(--mono);
            font-size:12px;color:var(--sec);text-decoration:none;
            border:1px solid var(--border);border-radius:6px;
            padding:2px 10px">close ×</a>
        </div>
        <div id="cDetailsBody" style="color:var(--muted);
          font-size:12.5px">loading…</div>
      </div>`;
    box.querySelector("#cCloseDetails").addEventListener("click", (e) => {
      e.preventDefault();
      state.drill = { date };
      renderDrill(el);
      refreshModels(el);
    });
    fetch(`/api/consumption/events?date=${date}&hour=${hour}&` + qs(), {cache: "no-store"})
      .then((r) => r.json()).then((ev) => {
        el.querySelector("#cDetailsBody").innerHTML = ev.length
          ? eventsTable(ev)
          : `<div style="padding:24px;text-align:center;color:var(--muted)">
              no activity this hour</div>`;
      });
  }

  function crumbNav(el) {
    const back = el.querySelector("#cBack");
    if (back) back.addEventListener("click", (e) => {
      e.preventDefault(); state.drill = null;
      renderDrill(el); refreshModels(el); });
  }

  // small multiples: cache is ~99% of the stack, so the two stories get
  // their own panels and their own honest y scales (operator pick, Few rule)
  const PANELS = [
    ["context re-read", ["cache_read", "cache_create"]],
    ["fresh work", ["input", "output"]],
  ];
  const COMP = Object.fromEntries(COMPONENTS.map(
    ([k, label, v]) => [k, { label, v }]));

  function drawChart(wrap, labels, rows, onClick, selected = -1) {
    charts.forEach((c) => c.destroy());
    charts = [];
    const legend = document.getElementById("cLegend");
    legend.innerHTML = COMPONENTS.map(([k, label, v]) =>
      `<span data-comp="${k}" data-tip="Click to hide/show this component
        within its panel."
        style="cursor:pointer;opacity:${state.hidden.has(k) ? ".35" : "1"}">
      <i style="display:inline-block;width:9px;height:9px;` +
      `border-radius:2px;background:${css(v)};margin-right:5px"></i>${label}</span>`
    ).join("");
    wrap.innerHTML = PANELS.map(([title], pi) => `
      <div class="kicker" style="padding:${pi ? "12px" : "0"} 0 2px">${title}
      </div><div style="position:relative;height:104px;width:100%">
      <canvas></canvas></div>`).join("");
    const canvases = wrap.querySelectorAll("canvas");
    PANELS.forEach(([, keys], pi) => {
      charts.push(new Chart(canvases[pi], {
        type: "bar",
        data: { labels,
          datasets: keys.map((k) => ({
            label: COMP[k].label, data: rows.map((r) => r[k]),
            backgroundColor: css(COMP[k].v), stack: "t", borderRadius: 2,
            maxBarThickness: 56, borderColor: "#0a0a0a",
            borderWidth: rows.map((_, i) => i === selected ? 1.5 : 0),
            hidden: state.hidden.has(k) })) },
        options: {
          maintainAspectRatio: false,
          animation: state.animated ? false : { duration: 500 },
          plugins: { legend: { display: false }, tooltip: {
            callbacks: { label: (c) =>
              `${c.dataset.label}: ${fmtTok(c.raw)}` } } },
          onClick: (e, els) => { if (els.length) onClick(els[0].index); },
          scales: {
            x: { stacked: true, grid: { display: false },
                 ticks: { display: pi === PANELS.length - 1,
                          font: { family: "ui-monospace, Menlo",
                                  size: 10.5 } } },
            y: { stacked: true, grid: { color: "var(--row)" },
                 border: { display: false },
                 ticks: { callback: (v) => fmtTok(v), maxTicksLimit: 4,
                          font: { family: "ui-monospace, Menlo",
                                  size: 10.5 } } },
          },
        },
      }));
    });
    legend.querySelectorAll("[data-comp]").forEach((sp) =>
      sp.addEventListener("click", () => {
        const k = sp.dataset.comp;
        state.hidden.has(k) ? state.hidden.delete(k) : state.hidden.add(k);
        const pi = PANELS.findIndex(([, keys]) => keys.includes(k));
        const di = PANELS[pi][1].indexOf(k);
        charts[pi].setDatasetVisibility(di, !state.hidden.has(k));
        charts[pi].update();
        sp.style.opacity = state.hidden.has(k) ? ".35" : "1";
      }));
    bindTips(legend);
    state.animated = true;  // one-time render animation only
  }

  function eventsTable(ev) {
    return `<table style="width:100%;border-collapse:collapse">
      <thead><tr>
        ${["session", "project", "consumer", "", "calls", "tokens", "duration"]
          .map((h, i) => `<th style="font-family:var(--sans);font-size:11px;
            letter-spacing:.05em;text-transform:uppercase;color:var(--sec);
            font-weight:600;text-align:${i > 2 ? "right" : "left"};
            padding:0 12px 8px 0;border-bottom:1px solid var(--border)">${h}</th>`)
          .join("")}</tr></thead>
      <tbody>${ev.map((e) => `<tr>
        <td class="num" style="padding:8px 12px 8px 0;color:var(--muted);
          font-size:11px">${e.session.slice(0, 8)}…</td>
        <td class="num" style="font-size:12px">${projLabel(e.project, projectIds)}</td>
        <td class="num" style="font-size:12px">${e.consumer}</td>
        <td><span style="font-family:var(--mono);font-size:10px;
          text-transform:uppercase;border-radius:6px;padding:2px 9px;
          background:${tagCSS(e.type)}">
          ${e.type}</span></td>
        <td class="num" style="text-align:right">${e.calls}</td>
        <td class="num" style="text-align:right">${fmtTok(e.tokens)}</td>
        <td class="num" style="text-align:right">${e.duration_ms ?
          (e.duration_ms / 1000).toFixed(1) + "s" : "—"}</td>
      </tr>`).join("")}</tbody></table>`;
  }

  function renderLeague(el, rows) {
    rows = [...rows].sort((a, b) => b[state.sortKey] - a[state.sortKey]);
    const maxA = Math.max(...rows.map((r) => r.session_tokens), 1);
    const maxB = Math.max(...rows.map((r) => r.message_tokens), 1);
    const sortMark = (k) => state.sortKey === k ? " ▾" : "";
    const sortable = (k) => `data-sort="${k}" style="cursor:pointer;` +
      (state.sortKey === k ? "color:var(--ink);" : "") + `"`;
    const flag = (f) => f === "agree"
      ? `<span data-tip="${FLAG_TIPS.agree}" style="font-size:11px;
          font-weight:600;background:var(--ok-bg);color:var(--ok-text);
          border-radius:6px;padding:2px 8px">high on both counts</span>`
      : f ? `<span data-tip="${FLAG_TIPS[f]}" style="font-size:11px;
          font-weight:600;background:${f === "n1" ? "var(--red-bg)"
            : "var(--tag-yellow-bg)"};color:${f === "n1" ? "var(--red)"
            : "var(--tag-yellow)"};border-radius:6px;padding:2px 8px">
          ${f === "n1" ? "seen once" : "counts disagree"}</span>` : "";
    const bar = (v, mx, dim) => `<span style="display:inline-block;height:8px;
      border-radius:2px;background:var(--ink);opacity:${dim ? ".45" : ".85"};
      width:${Math.max(v / mx * 120, 2)}px;margin-right:8px;vertical-align:1px">
      </span>`;
    let shown;
    el.querySelector("#cLeague").innerHTML = `
      <table style="width:100%;border-collapse:collapse">
      <thead><tr>
        <th style="text-align:left;font-family:var(--sans);font-size:11px;
          letter-spacing:.05em;text-transform:uppercase;color:var(--sec);
          font-weight:600;padding-bottom:8px;border-bottom:1px solid var(--border)">
          <span data-tip="Anything that uses your tokens and that you
          could act on — a skill, an MCP server, or a program you installed."
          style="border-bottom:1px dotted var(--muted);cursor:help"
          >consumer</span></th>
        <th></th>
        <th style="text-align:right;font-family:var(--sans);font-size:11px;
          letter-spacing:.05em;text-transform:uppercase;color:var(--sec);
          font-weight:600;border-bottom:1px solid var(--border)">
          <span ${sortable("sessions")}>sessions${sortMark("sessions")}</span></th>
        <th style="text-align:right;font-family:var(--sans);font-size:11px;
          letter-spacing:.05em;text-transform:uppercase;color:var(--sec);
          font-weight:600;border-bottom:1px solid var(--border)">
          <span data-tip="${LENS_A_TIP}" ${sortable("session_tokens")}>
          <span style="border-bottom:1px dotted var(--muted)">whole
          session tokens</span>${sortMark("session_tokens")}</span></th>
        <th style="text-align:right;font-family:var(--sans);font-size:11px;
          letter-spacing:.05em;text-transform:uppercase;color:var(--sec);
          font-weight:600;border-bottom:1px solid var(--border)">
          <span data-tip="${LENS_B_TIP}" ${sortable("message_tokens")}>
          <span style="border-bottom:1px dotted var(--muted)">direct message
          tokens</span>${sortMark("message_tokens")}</span></th>
        <th style="text-align:right;font-family:var(--sans);font-size:11px;
          letter-spacing:.05em;text-transform:uppercase;color:var(--sec);
          font-weight:600;border-bottom:1px solid var(--border)">
          uses · last 14 days</th>
        <th style="border-bottom:1px solid var(--border)"></th></tr></thead>
      <tbody>${(shown = rows.slice(0, 30)
        // pinned: every demoted item stays restorable past the row cut
        .concat(rows.slice(30).filter((r) => state.demoted.has(r.consumer))))
        .map((r, ri) => {
        const demoted = r.type === "shell" && state.demoted.has(r.consumer);
        const ov = r.type === "cli"
          ? ` data-ov="1" data-consumer="${r.consumer}" data-tip="Click to move
              to shell utilities — out of this default view, restorable there.
              Saved to ~/.ccwhere/overrides.json" style="cursor:pointer;`
          : demoted
          ? ` data-ov="0" data-consumer="${r.consumer}" data-tip="Moved out by
              you — click to restore to the default view" style="cursor:pointer;
              border:1px dashed var(--muted);`
          : ` style="`;
        return `<tr>
        <td class="num" style="padding:9px 12px 9px 0;font-size:12.5px;
          border-bottom:1px solid var(--row)">${r.consumer}</td>
        <td style="border-bottom:1px solid var(--row)"><span${ov}
          font-family:var(--mono);font-size:10px;text-transform:uppercase;
          border-radius:6px;padding:2px 9px;background:${tagCSS(r.type)}">${
            demoted ? "shell ·you" : r.type}</span></td>
        <td class="num" style="text-align:right;font-size:12px;
          border-bottom:1px solid var(--row)">${r.sessions}</td>
        <td class="num" style="text-align:right;font-size:12px;white-space:nowrap;
          border-bottom:1px solid var(--row)">${bar(r.session_tokens, maxA)}
          ${fmtTok(r.session_tokens)}</td>
        <td class="num" style="text-align:right;font-size:12px;white-space:nowrap;
          border-bottom:1px solid var(--row)">${bar(r.message_tokens, maxB, 1)}
          ${fmtTok(r.message_tokens)}</td>
        <td class="cSpark" data-i="${ri}" data-tip="Click to enlarge with
          dated axes" style="text-align:right;cursor:pointer;
          border-bottom:1px solid var(--row)">
          ${sparkSVG(r.spark)}</td>
        <td style="text-align:right;border-bottom:1px solid var(--row)">
          ${flag(r.flag)}</td>
      </tr>`; }).join("")}</tbody></table>`;
    el.querySelectorAll("td.cSpark").forEach((c) =>
      c.addEventListener("click", () => {
        const [, to] = presetRange(state.preset);
        const r = shown[+c.dataset.i];
        window.ccw.sparkZoomRow(c.parentElement,
          {counts: r.spark, tokens: r.spark_tok}, to, 7);
      }));
    el.querySelectorAll("[data-sort]").forEach((h) =>
      h.addEventListener("click", () => {
        state.sortKey = h.dataset.sort;
        renderLeague(el, rows);
      }));
    el.querySelectorAll("[data-ov]").forEach((t) =>
      t.addEventListener("click", async () => {
        await fetch("/api/overrides", {method: "POST", cache: "no-store",
          body: JSON.stringify({consumer: t.dataset.consumer,
                                demoted: t.dataset.ov === "1"})});
        load(el);
      }));
    bindTips(el);
  }

  window.renderConsumption = render;
})();
