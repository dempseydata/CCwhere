/* Live tab: what is running now. Read-only by constitution — no kill,
   pause, open, or navigate affordances, ever (live-view spec). */
"use strict";

(function () {
  const { projLabel, bindTips } = window.ccw;

  const fmtAge = (s) => s < 90 ? `${Math.round(s)}s ago`
    : `${Math.round(s / 60)} min ago`;
  const dirLabel = (cwd) => cwd.split("/").filter(Boolean).slice(-2).join("/");

  const row = (r) => `
    <div style="display:grid;grid-template-columns:14px 220px 1fr 160px
      110px;gap:14px;align-items:baseline;padding:13px 0;
      border-bottom:1px solid #F2F1EE">
      <span style="width:9px;height:9px;border-radius:50%;align-self:center;
        ${r.state === "running" ? "background:#3E9464"
          : "border:1.5px solid #B8B6B0"}"></span>
      <span style="font-family:var(--mono);font-size:12.5px">
        ${projLabel(r.project)}</span>
      <span style="font-size:12.5px;color:var(--sec)">${r.activity}
        <span style="font-family:var(--mono);font-size:10.5px;
          color:var(--muted)"> · ${r.session.slice(0, 8)}</span></span>
      <span style="font-family:var(--mono);font-size:11px;
        color:var(--sec)">${r.model || ""}</span>
      <span class="num" style="font-size:12px;text-align:right">
        ${fmtAge(r.age_s)}</span>
    </div>`;

  async function render(el) {
    el.innerHTML = `
      <div class="kicker">Live · disk truth · scanned at page load</div>
      <h1 style="margin-bottom:2px">What is running now</h1>
      <div style="font-size:12.5px;color:var(--sec);margin-bottom:14px">
        Read-only: observe, never touch. Liveness from session-file writes —
        independent of sync.</div>
      <div id="lvOpen" style="margin-bottom:18px"></div>
      <div id="lvList" style="color:var(--muted)">looking…</div>`;
    const d = await (await fetch("/api/live", {cache: "no-store"})).json();

    el.querySelector("#lvOpen").innerHTML = !d.open.length ? "" :
      `<span style="font-family:var(--mono);font-size:11px;
         color:var(--muted)">open windows</span> ` +
      d.open.map((o) => `<span data-tip="From the process table (ps + lsof),
        read-only. An open window that isn't conversing writes no history,
        so it cannot be matched to a specific session — counted per
        directory." style="font-family:var(--mono);font-size:11.5px;
        border:1px solid var(--border);border-radius:9999px;
        padding:3px 11px;margin-left:6px;color:var(--sec);cursor:help">
        ${dirLabel(o.cwd)} × ${o.count}</span>`).join("");

    const running = d.sessions.filter((r) => r.state === "running");
    const recent = d.sessions.filter((r) => r.state === "recent");
    const section = (title, rows) => !rows.length ? "" :
      `<div class="kicker" style="padding:14px 0 2px">${title}</div>` +
      rows.map(row).join("");
    el.querySelector("#lvList").innerHTML =
      (running.length || recent.length)
        ? section("Running now · wrote within 5 min", running) +
          section("Recently active · 5–15 min ago", recent)
        : `<div style="border:1px dashed var(--border);border-radius:8px;
             padding:26px;text-align:center;color:var(--muted);
             font-size:13px">Nothing running — no session file changed in
             the last 15 minutes.</div>`;
    bindTips(el);
  }

  window.renderLive = render;
})();
