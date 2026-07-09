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
    return `font-family:var(--mono);font-size:11.5px;border-radius:9999px;` +
      `padding:4px 12px;cursor:pointer;border:1px solid ` +
      (on ? "#111;background:#111;color:#fff" :
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
    tip.style.cssText = "position:fixed;pointer-events:none;background:#111;" +
      "color:#fff;font-family:var(--mono);font-size:11px;line-height:1.5;" +
      "padding:8px 10px;border-radius:6px;opacity:0;transition:opacity .12s;" +
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

  return { PRESETS, presetRange, chipCSS, projLabel, tagCSS, bindTips };
})();
