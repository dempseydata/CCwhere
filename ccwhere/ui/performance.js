/* Performance tab: per-tool latency percentiles and error rates (story 6). */
"use strict";

(function () {
  const { PRESETS, chipCSS, projLabel, tagCSS, bindTips } = window.ccw;

  const state = { preset: "30d", from: null, to: null,
                  projects: new Set(), sortKey: "p95" };
  let projectIds = [];

  const fmtMs = (ms) => ms == null ? "—"
    : ms >= 60000 ? (ms / 60000).toFixed(1) + "m"
    : ms >= 1000 ? (ms / 1000).toFixed(1) + "s" : ms + "ms";

  function renderFilters(el) {
    const bar = el.querySelector("#pFiltersTime");
    const projBar = el.querySelector("#pFiltersProj");
    bar.innerHTML = PRESETS.map(([k, label]) =>
      `<span data-preset="${k}" style="${chipCSS(state.preset === k)}">${label}</span>`
    ).join("") +
      (state.preset === "custom"
        ? ` <input type="date" id="pFrom" value="${state.from || ""}">
            <input type="date" id="pTo" value="${state.to || ""}">` : "");
    projBar.innerHTML = projectIds.map((p) =>
      `<span data-proj="${p}" style="${chipCSS(state.projects.has(p))}">` +
      `${projLabel(p)}</span>`).join("");
    projBar.querySelectorAll("[data-proj]").forEach((c) =>
      c.addEventListener("click", () => {
        const p = c.dataset.proj;
        state.projects.has(p) ? state.projects.delete(p) : state.projects.add(p);
        renderFilters(el); load(el);
      }));
    bar.querySelectorAll("[data-preset]").forEach((c) =>
      c.addEventListener("click", () => {
        state.preset = c.dataset.preset;
        renderFilters(el);
        if (state.preset !== "custom" || (state.from && state.to)) load(el);
      }));
    ["pFrom", "pTo"].forEach((id) => {
      const i = bar.querySelector("#" + id);
      if (i) i.addEventListener("change", () => {
        state.from = bar.querySelector("#pFrom").value || null;
        state.to = bar.querySelector("#pTo").value || null;
        if (state.from && state.to) load(el);
      });
    });
  }

  function qs() {
    const [from, to] = window.ccw.presetRange(state.preset,
                                              [state.from, state.to]);
    const p = new URLSearchParams();
    if (from) p.set("from", from);
    if (to) p.set("to", to);
    if (state.projects.size) p.set("projects", [...state.projects].join(","));
    return p.toString();
  }

  function renderTable(el, rows) {
    const keys = [["calls", "calls"], ["err_rate", "errors"],
                  ["p50", "typical", "Median (p50) — half of calls were faster"],
                  ["p95", "worst 5%", "p95 — 5% of calls were slower than this"],
                  ["max", "worst", "The single slowest call"]];
    rows = [...rows].sort((a, b) =>
      (b[state.sortKey] ?? -1) - (a[state.sortKey] ?? -1));
    const th = (k, label, tip) => `<th style="text-align:right;
        font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;
        text-transform:uppercase;color:var(--muted);font-weight:500;
        border-bottom:1px solid var(--border)">
        <span data-sort="${k}"${tip ? ` data-tip="${tip}"` : ""}
          style="cursor:pointer">${label}${
          state.sortKey === k ? " ▾" : ""}</span></th>`;
    el.querySelector("#pTable").innerHTML = `
      <table style="width:100%;border-collapse:collapse">
      <thead><tr>
        <th style="text-align:left;font-family:var(--mono);font-size:10.5px;
          letter-spacing:.06em;text-transform:uppercase;color:var(--muted);
          font-weight:500;padding-bottom:8px;
          border-bottom:1px solid var(--border)">tool</th>
        <th style="border-bottom:1px solid var(--border)"></th>
        ${keys.map(([k, l, tip]) => th(k, l, tip)).join("")}
        <th style="border-bottom:1px solid var(--border)"></th></tr></thead>
      <tbody>${rows.slice(0, 40).map((r) => `<tr>
        <td class="num" style="padding:8px 12px 8px 0;font-size:12.5px;
          border-bottom:1px solid #F2F1EE">${r.consumer}</td>
        <td style="border-bottom:1px solid #F2F1EE"><span style="
          font-family:var(--mono);font-size:10px;text-transform:uppercase;
          border-radius:9999px;padding:2px 9px;background:${tagCSS(r.type)}">
          ${r.type}</span></td>
        <td class="num" style="text-align:right;font-size:12px;
          border-bottom:1px solid #F2F1EE">${r.calls}</td>
        <td class="num" style="text-align:right;font-size:12px;
          border-bottom:1px solid #F2F1EE;${r.err_rate
            ? "color:var(--red);font-weight:600" : "color:var(--muted)"}"
          ${r.err_rate ? `data-tip="${r.errors} of ${r.calls} calls errored"`
                       : ""}>${r.err_rate
            ? (r.err_rate * 100).toFixed(1) + "%" : "—"}</td>
        <td class="num" style="text-align:right;font-size:12px;
          border-bottom:1px solid #F2F1EE">${fmtMs(r.p50)}</td>
        <td class="num" style="text-align:right;font-size:12px;font-weight:600;
          border-bottom:1px solid #F2F1EE">${fmtMs(r.p95)}</td>
        <td class="num" style="text-align:right;font-size:12px;
          color:var(--sec);border-bottom:1px solid #F2F1EE">${fmtMs(r.max)}</td>
        <td style="text-align:right;border-bottom:1px solid #F2F1EE">${
          r.n_paired < 10 ? `<span data-tip="Only ${r.n_paired} calls
            returned with a measurable time — weak evidence at this sample
            size." style="font-family:var(--mono);font-size:10px;
            background:var(--tag-yellow-bg);color:var(--tag-yellow);
            border-radius:9999px;padding:2px 8px;white-space:nowrap">
            only ${r.n_paired} timed calls</span>` : ""}</td>
      </tr>`).join("")}</tbody></table>`;
    el.querySelectorAll("[data-sort]").forEach((h) =>
      h.addEventListener("click", () => {
        state.sortKey = h.dataset.sort;
        renderTable(el, rows);
      }));
    bindTips(el);
  }

  async function load(el) {
    const r = await fetch("/api/performance?" + qs(), {cache: "no-store"});
    const data = await r.json();
    if (!projectIds.length && data.projects) {
      projectIds = data.projects; renderFilters(el);
    }
    renderTable(el, data.rows);
  }

  function render(el) {
    el.innerHTML = `
      <div id="pFiltersTime" style="display:flex;align-items:center;gap:8px;
        flex-wrap:wrap;margin-bottom:10px"></div>
      <div id="pFiltersProj" style="display:flex;align-items:center;gap:8px;
        flex-wrap:wrap;margin-bottom:20px"></div>
      <div class="kicker">Performance · how long tools take</div>
      <h1 style="margin-bottom:2px">What is slow or failing</h1>
      <div style="font-size:12.5px;color:var(--sec);margin-bottom:14px">
        Times count only <span data-tip="A call whose result never came
        back (crashed session, or past the 10-minute cap) counts as a call
        but never gets an invented time." style="border-bottom:1px
        dotted var(--muted);cursor:help">calls whose result came back</span>.
        MCP servers break out per tool — the Consumers table is where you
        prune servers; this table finds slow tools.</div>
      <div id="pTable" style="color:var(--muted)">loading…</div>`;
    renderFilters(el);
    bindTips(el);
    load(el);
  }

  window.renderPerformance = render;
})();
