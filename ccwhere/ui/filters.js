/* Shared UI primitives: filter presets, chips, labels, tags, tooltips.
   Promoted from consumption.js when performance.js became the second
   consumer (two-tier rule). */
"use strict";

window.ccw = (function () {
  const PRESETS = [["today", "Today"], ["yesterday", "Yesterday"],
    ["week", "This week"], ["lastweek", "Last week"], ["month", "This month"],
    ["30d", "30d"], ["custom", "Custom"]];

  const iso = (d) => d.toLocaleDateString("sv-SE");
  function presetRange(p, custom) {
    const now = new Date(); const today = iso(now);
    const shift = (n) => iso(new Date(now.getFullYear(), now.getMonth(),
                                      now.getDate() - n));
    const monday = (d) => { const x = new Date(d);
      x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); return x; };
    switch (p) {
      case "today": return [today, today];
      case "yesterday": return [shift(1), shift(1)];
      case "week": return [iso(monday(now)), today];
      case "lastweek": { const m = monday(now);
        const s = new Date(m); s.setDate(s.getDate() - 7);
        const e = new Date(m); e.setDate(e.getDate() - 1);
        return [iso(s), iso(e)]; }
      case "month": return [iso(new Date(now.getFullYear(), now.getMonth(), 1)),
                            today];
      case "30d": return [shift(29), today];
      default: return custom || [null, null];
    }
  }

  function chipCSS(on) {
    return `font-family:var(--sans);font-size:12.5px;font-weight:500;border-radius:9999px;` +
      `padding:4px 12px;cursor:pointer;border:1px solid ` +
      (on ? "#111;background:#1c1c1e;color:#fff" :
            "var(--border);background:var(--card);color:var(--sec)");
  }

  const projLabel = (id) => {
    const s = id
      .replace(/^-?Users-[^-]+-(Documents-Claude-)?/, "")
      .replace(/^Library-Application-Support-/, "")
      .replace(/^-?Applications-/, "");
    return s.length > 26 ? s.slice(0, 24) + "…" : s;
  };

  const tagCSS = (t) =>
    t === "mcp" ? "var(--tag-blue-bg);color:var(--tag-blue)"
    : t === "cli" ? "var(--tag-green-bg);color:var(--tag-green)"
    : t === "shell" || t === "builtin" ? "#F2F1EE;color:var(--sec)"
    : "var(--tag-yellow-bg);color:var(--tag-yellow)";

  /* single tooltip layer shared by every tab */
  let tip = document.getElementById("tip");
  if (!tip) {
    tip = document.createElement("div"); tip.id = "tip";
    tip.style.cssText = "position:fixed;pointer-events:none;background:#1c1c1e;" +
      "color:#fff;font-family:var(--mono);font-size:11px;line-height:1.5;" +
      "padding:8px 10px;border-radius:8px;opacity:0;transition:opacity .12s;" +
      "z-index:9;max-width:240px";
    document.body.appendChild(tip);
  }
  function bindTips(root) {
    root.querySelectorAll("[data-tip]").forEach((el) => {
      el.addEventListener("mousemove", (e) => {
        tip.textContent = el.dataset.tip; tip.style.opacity = 1;
        tip.style.left = Math.min(e.clientX + 14, innerWidth - 250) + "px";
        tip.style.top = (e.clientY - 10) + "px";
      });
      el.addEventListener("mouseleave", () => { tip.style.opacity = 0; });
    });
  }

  const fmtTok = (n) => n == null ? "—"
    : n >= 1e9 ? (n / 1e9).toFixed(1) + "B"
    : n >= 1e6 ? (n / 1e6).toFixed(1) + "M"
    : n >= 1e3 ? (n / 1e3).toFixed(0) + "K" : String(n);

  /* click-to-enlarge for 14-day sparklines: toggles an inserted full-width
     row with a dated Chart.js bar chart (readable x/y, spark has neither).
     series = {counts, tokens} — tokens optional; when present, mode chips
     switch between invocations/day and direct message tokens/day. */

  function sparkZoomRow(tr, series, endISO, colspan) {
    const next = tr.nextElementSibling;
    if (next && next.classList.contains("sparkRow")) {
      if (next._chart) next._chart.destroy();
      next.remove();
      return;
    }
    const MODES = [
      ["counts", "uses / day", { precision: 0 }],
      ["tokens", "direct message tokens / day",
       { callback: (v) => fmtTok(v) }],
    ].filter(([k]) => series[k]);
    const row = document.createElement("tr");
    row.className = "sparkRow";
    const td = document.createElement("td");
    td.colSpan = colspan;
    td.innerHTML = `<div style="max-width:560px;margin:8px 0 14px;
      padding:10px 12px 6px;border:1.5px solid var(--panel-border);border-radius:8px">
      <div class="zoomModes" style="display:flex;gap:6px;
        justify-content:flex-end;margin-bottom:4px"></div>
      <div style="height:150px"><canvas></canvas></div></div>`;
    row.appendChild(td);
    tr.after(row);
    const [y, m, d] = (endISO || new Date().toLocaleDateString("sv-SE"))
      .split("-").map(Number);
    const labels = [...Array(14)].map((_, i) => {
      const dt = new Date(y, m - 1, d - (13 - i));
      return `${String(dt.getMonth() + 1).padStart(2, "0")}-${
        String(dt.getDate()).padStart(2, "0")}`;
    });
    let mode = 0;
    row._chart = new Chart(td.querySelector("canvas"), {
      type: "bar",
      data: { labels, datasets: [{ data: series[MODES[0][0]],
        backgroundColor: "#787774", borderRadius: 2 }] },
      options: { maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: MODES[0][2],
               title: { display: true, text: MODES[0][1] } },
          x: { grid: { display: false } } } },
    });
    const modesBox = td.querySelector(".zoomModes");
    function drawModes() {
      modesBox.innerHTML = MODES.length < 2 ? "" : MODES.map(([, label], i) =>
        `<span data-mode="${i}" style="${chipCSS(i === mode)};
          font-size:10.5px;padding:2px 10px">${label}</span>`).join("");
      modesBox.querySelectorAll("[data-mode]").forEach((c) =>
        c.addEventListener("click", (ev) => {
          ev.stopPropagation();
          mode = +c.dataset.mode;
          const [key, title, ticks] = MODES[mode];
          row._chart.data.datasets[0].data = series[key];
          row._chart.options.scales.y.title.text = title;
          row._chart.options.scales.y.ticks = { beginAtZero: true, ...ticks };
          row._chart.update();
          drawModes();
        }));
    }
    drawModes();
  }

  return { PRESETS, presetRange, chipCSS, projLabel, tagCSS, bindTips,
           sparkZoomRow, fmtTok };
})();
