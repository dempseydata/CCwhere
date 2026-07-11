/* ccwhere shell: tab switching, refresh round-trip, canary, auto-refresh. */
"use strict";

// Inventory retired 2026-07-08: story 10 is delivered by the ledger drill
const TABS = {
  consumption: "Consumption",
  ledger: "Context ledger",
  performance: "Performance",
  live: "Live",
};

const $ = (id) => document.getElementById(id);

async function getJSON(path, opts) {
  const r = await fetch(path, Object.assign({cache: "no-store"}, opts));
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

function fmtAge(s) {
  if (s == null) return "never synced";
  if (s < 90) return `synced ${Math.round(s)}s ago`;
  if (s < 5400) return `synced ${Math.round(s / 60)} min ago`;
  return `synced ${(s / 3600).toFixed(1)}h ago`;
}

async function renderHeader() {
  const h = await getJSON("/api/health");
  $("syncAge").textContent = fmtAge(h.last_sync_age_s);
  const c = $("canary");
  if (h.drift_pct != null && h.drift_pct > h.canary_threshold_pct) {
    c.innerHTML = `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--red);margin-right:5px"></span>${h.drift_pct}% of the history couldn't be read — Claude Code's file format may have changed; update ccwhere`;
    c.className = "firing";
  } else {
    c.innerHTML = `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--ok);margin-right:5px"></span>all history readable`;
    c.className = "";
  }
}

/* Tab bodies: placeholders until each tab's change lands. */
async function renderTab(tab) {
  const main = $("main");
  document.querySelectorAll("#nav a").forEach((a) =>
    a.classList.toggle("on", a.hash === `#${tab}`));
  if (tab === "consumption") {
    window.renderConsumption(main);
  } else if (tab === "ledger") {
    window.renderLedger(main);
  } else if (tab === "performance") {
    window.renderPerformance(main);
  } else if (tab === "live") {
    window.renderLive(main);
  } else {
    main.innerHTML = `
      <div class="kicker">${TABS[tab] || ""}</div>
      <h1>${TABS[tab] || "Not found"}</h1>
      <div class="placeholder">This tab arrives in a later change.</div>`;
  }
}

function currentTab() {
  const t = location.hash.replace("#", "");
  return TABS[t] ? t : "consumption";
}

async function refresh() {
  const btn = $("refresh");
  btn.disabled = true;
  btn.textContent = "Syncing…";
  try {
    await getJSON("/api/sync", { method: "POST" });
    await renderHeader();
    await renderTab(currentTab());
  } finally {
    btn.disabled = false;
    btn.textContent = "Refresh";
  }
}

/* auto-refresh: off by default, persisted */
let autoTimer = null;
function setAuto(on) {
  localStorage.setItem("ccwhere:auto", on ? "1" : "0");
  if (autoTimer) clearInterval(autoTimer);
  autoTimer = on ? setInterval(refresh, 30000) : null;
}

$("refresh").addEventListener("click", refresh);
$("autoRefresh").addEventListener("change", (e) => setAuto(e.target.checked));
window.addEventListener("hashchange", () => renderTab(currentTab()));

const auto = localStorage.getItem("ccwhere:auto") === "1";
$("autoRefresh").checked = auto;
setAuto(auto);
renderHeader();
renderTab(currentTab());
