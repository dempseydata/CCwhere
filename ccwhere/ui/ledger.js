/* Context ledger tab: measured medians, honest decomposition, inventory. */
"use strict";

(function () {
  const HATCH = "repeating-linear-gradient(45deg,#DDDBD6 0 3px,#F4F2ED 3px 6px)";

  const fmtK = (n) => n == null ? "—" : (n / 1000).toFixed(1) + "K";
  const label = (p) => {
    if (!p.cwd) return p.project.replace(/^-?Users-[^-]+-(Documents-)?/, "");
    const parts = p.cwd.split("/").filter(Boolean);
    return parts.slice(-2).join("/");
  };

  let tip = document.getElementById("tip");
  function bindTips(root) {
    if (!tip) {
      tip = document.createElement("div"); tip.id = "tip";
      tip.style.cssText = "position:fixed;pointer-events:none;background:#111;" +
        "color:#fff;font-family:var(--mono);font-size:11px;line-height:1.5;" +
        "padding:8px 10px;border-radius:6px;opacity:0;transition:opacity .12s;" +
        "z-index:9;max-width:240px";
      document.body.appendChild(tip);
    }
    root.querySelectorAll("[data-tip]").forEach((el) => {
      el.addEventListener("mousemove", (e) => {
        tip.textContent = el.dataset.tip; tip.style.opacity = 1;
        tip.style.left = Math.min(e.clientX + 14, innerWidth - 250) + "px";
        tip.style.top = (e.clientY - 10) + "px";
      });
      el.addEventListener("mouseleave", () => { tip.style.opacity = 0; });
    });
  }

  const TAG_CSS = {
    prunable: "background:var(--tag-yellow-bg);color:var(--tag-yellow)",
    fixed: "background:#F2F1EE;color:var(--sec)",
    unknown: "background:var(--red-bg);color:var(--red)",
  };
  const tag = (t, text) => `<span style="font-family:var(--mono);font-size:10px;
    letter-spacing:.05em;text-transform:uppercase;border-radius:9999px;
    padding:2px 9px;white-space:nowrap;${TAG_CSS[t]}">${text}</span>`;

  function sparkSVG(arr) {
    const mx = Math.max(...arr, 1);
    return `<svg width="70" height="17" viewBox="0 0 70 17">` + arr.map((v, i) =>
      v ? `<rect x="${i * 5}" y="${16 - v / mx * 13}" width="4"
             height="${(v / mx * 13 + 2).toFixed(1)}" fill="#787774" rx="1"/>`
        : `<rect x="${i * 5}" y="14.5" width="4" height="1.5" fill="#E3E1DC"/>`
    ).join("") + `</svg>`;
  }

  function skillStatus(u) {
    if (!u || !u.uses) return tag("prunable", "never used");
    const days = (Date.now() - new Date(u.last)) / 864e5;
    return days > 30 ? tag("prunable", "stale >30d") : tag("fixed", "active");
  }

  function skillRows(skills) {
    const maxT = Math.max(...skills.map((s) => s.tokens), 1);
    // group by package; packages ordered by never-used cost (the uninstall
    // decision), rows within already in prune-priority order from the API
    const groups = new Map();
    skills.forEach((s) => {
      const k = s.pkg || "(project)";
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(s);
    });
    const unused = (list) => list.reduce((t, s) =>
      t + (s.usage && s.usage.uses ? 0 : s.tokens), 0);
    const ordered = [...groups.entries()]
      .sort((a, b) => unused(b[1]) - unused(a[1]));
    return `<div style="margin:4px 0 10px 24px;border-left:2px solid
      var(--border);padding-left:14px">
      <div class="kicker" style="padding:4px 0 6px">per skill · grouped by
        package, most never-used cost first</div>
      <table style="width:100%;border-collapse:collapse">` +
      ordered.map(([pkg, list]) => `<tr>
        <td colspan="7" style="padding:14px 0 6px">
          <div style="background:#EDEBE6;border-radius:4px;padding:5px 10px;
            font-family:var(--mono);font-size:11.5px;font-weight:700;
            letter-spacing:.07em;text-transform:uppercase">
            ${pkg}
            <span style="font-weight:400;color:var(--sec);text-transform:none;
              letter-spacing:0"> · ${list.length} skills ·
            ${list.reduce((t, s) => t + s.tokens, 0)} tok ·
            <b>${unused(list)} tok never-used</b></span></div></td></tr>` +
        list.map((s) => `<tr>
        <td style="font-family:var(--mono);font-size:11.5px;width:250px;
          padding:4px 12px 4px 0;border-bottom:1px solid #F7F6F3">
          ${s.name}${s.kind === "command"
            ? ` <span style="color:var(--muted);font-size:9.5px">· cmd</span>`
            : ""}</td>
        <td style="width:130px;border-bottom:1px solid #F7F6F3">
          <div style="height:6px;border-radius:2px;background:#B8B6B0;width:${
            Math.max(s.tokens / maxT * 110, 2).toFixed(0)}px"></div></td>
        <td class="num" style="font-size:11.5px;text-align:right;width:60px;
          border-bottom:1px solid #F7F6F3">${s.tokens} tok</td>
        <td class="num" style="font-size:11.5px;text-align:right;width:50px;
          border-bottom:1px solid #F7F6F3">${s.usage ? s.usage.uses : 0}</td>
        <td style="text-align:right;width:80px;
          border-bottom:1px solid #F7F6F3">${sparkSVG(
            (s.usage && s.usage.spark) || Array(14).fill(0))}</td>
        <td class="num" style="font-size:11px;text-align:right;width:110px;
          color:var(--sec);border-bottom:1px solid #F7F6F3">${
            !(s.usage && s.usage.last) ? "—"
            : (s.usage.first && s.usage.first !== s.usage.last)
              ? `${s.usage.first.slice(5)} → ${s.usage.last.slice(5)}`
              : s.usage.last.slice(5)}</td>
        <td style="text-align:right;width:100px;
          border-bottom:1px solid #F7F6F3">${skillStatus(s.usage)}</td>
      </tr>`).join("")).join("") + `</table></div>`;
  }

  function invTable(items, barCss, maxTok) {
    return `<table style="width:100%;border-collapse:collapse">` +
      items.map((it, i) => `<tr${it.skills ? ` class="drillable"
          data-d="${i}" style="cursor:pointer"` : ""}>
        <td style="font-family:var(--mono);font-size:12px;
          padding:6px 12px 6px 0;border-bottom:1px solid #F7F6F3;
          width:240px">${it.skills
            ? `<span class="ichev" style="color:var(--muted)">▸</span> ` : ""}
          ${it.name}</td>
        <td style="width:190px;border-bottom:1px solid #F7F6F3">
          <div style="height:7px;border-radius:2px;${barCss};width:${
            it.tokens ? Math.max(it.tokens / maxTok * 170, 2).toFixed(0) : 2
          }px"></div></td>
        <td class="num" style="font-size:12px;text-align:right;width:70px;
          white-space:nowrap;border-bottom:1px solid #F7F6F3">${
            it.tokens == null ? "—" : fmtK(it.tokens)}</td>
        <td style="color:var(--sec);font-size:12px;padding-left:12px;
          border-bottom:1px solid #F7F6F3">${it.note}${it.skills
            ? " · click to drill" : ""}</td>
        <td style="text-align:right;border-bottom:1px solid #F7F6F3">${
          tag(it.tag, it.tag === "prunable" ? "prunable" :
              it.tag === "fixed" ? "fixed cost" : "unknown")}</td>
      </tr>` + (it.skills ? `<tr class="idrill" style="display:none">
        <td colspan="5" style="padding:0">${skillRows(it.skills)}</td>
      </tr>` : "")).join("") + `</table>`;
  }

  async function render(el) {
    el.innerHTML = `<div class="kicker">Context ledger · medians over all
      parent sessions</div>
      <h1 style="margin-bottom:2px">What sessions pay before work starts</h1>
      <div style="font-size:12.5px;color:var(--sec)">The
        <span data-tip="Median of each session's first API call context (input +
        cache read + cache create). This is what actually happened — the one
        number that cannot be wrong." style="border-bottom:1px dotted
        var(--muted);cursor:help">measured median</span> is authoritative.
        The inventory beneath it is a best-effort breakdown from files on disk —
        the <span data-tip="The share of measured context no file on disk
        predicts: session hook output, MCP server instructions, tool schemas,
        harness lists. Shown at full size, never normalized away."
        style="border-bottom:1px dotted var(--muted);cursor:help">unattributed
        share</span> is shown, never hidden.</div>
      <div style="display:flex;gap:16px;font-family:var(--mono);font-size:11px;
        color:var(--sec);margin:14px 0 4px">
        <span><i style="display:inline-block;width:9px;height:9px;
          border-radius:2px;background:#B8B6B0;margin-right:5px"></i>calibrated
          floor (shared)</span>
        <span><i style="display:inline-block;width:9px;height:9px;
          border-radius:2px;background:#2F3437;margin-right:5px"></i>itemized
          here (prunable)</span>
        <span><i style="display:inline-block;width:9px;height:9px;
          border-radius:2px;background:${HATCH};margin-right:5px"></i>
          unattributed</span>
      </div>
      <div id="lFloor"></div>
      <div id="lRows" style="color:var(--muted)">loading…</div>`;
    bindTips(el);
    const led = await (await fetch("/api/ledger", {cache: "no-store"})).json();
    const fMax = Math.max(...led.floor_items.map((i) => i.tokens || 0), 1);
    // story 10 headline: what uninstalling all dead weight would recover
    const unusedTot = led.floor_items.reduce((t, it) =>
      t + (it.skills || []).reduce((a, s) =>
        a + (s.usage && s.usage.uses ? 0 : s.tokens), 0), 0);
    el.querySelector("#lFloor").innerHTML = `
      <div class="kicker" style="padding:20px 0 6px">User level — loaded into
        every session, every project · calibrated floor ${fmtK(led.floor)}
        measured${unusedTot ? ` · <b style="color:var(--tag-yellow)">${
        fmtK(unusedTot)} never-used</b>` : ""}</div>
      ${invTable(led.floor_items, "background:#B8B6B0", fMax)}
      <div class="kicker" style="padding:22px 0 2px">Per project — what each
        working directory adds on top</div>`;
    const maxM = Math.max(...led.projects.map((p) => p.median), 1);
    const w = (v) => (v / maxM * 100).toFixed(1) + "%";
    el.querySelector("#lRows").innerHTML = led.projects.map((p, i) => {
      const maxTok = Math.max(
        ...p.items.map((it) => it.tokens || 0), p.unattributed, 1);
      const lowN = p.n < 3 ? ` <span style="font-family:var(--mono);
        font-size:10px;background:var(--tag-yellow-bg);color:var(--tag-yellow);
        border-radius:9999px;padding:2px 8px">low sample · N=${p.n}</span>` : "";
      return `<div style="border-bottom:1px solid #F2F1EE">
        <div class="lHead" data-i="${i}" style="display:grid;
          grid-template-columns:22px 240px 80px 1fr;gap:16px;
          align-items:center;padding:12px 0;cursor:pointer">
          <span class="chev" style="font-family:var(--mono);
            color:var(--muted);font-size:11px">▸</span>
          <span style="font-family:var(--mono);font-size:12.5px"
            data-tip="${p.cwd || p.project}">${label(p)}${lowN}</span>
          <span class="num" style="font-size:14px;font-weight:600;
            text-align:right">${fmtK(p.median)}</span>
          <span style="position:relative;height:12px">
            <span style="position:absolute;inset:0;display:flex;gap:2px">
              <span data-tip="calibrated floor: ${fmtK(p.floor)} — shared by
                every project on this machine" style="width:${w(p.floor)};
                background:#B8B6B0;border-radius:2px"></span>
              <span data-tip="itemized in this project: ${fmtK(p.itemized)} —
                open the row for the inventory" style="width:${w(p.itemized)};
                background:#2F3437;border-radius:2px"></span>
              <span data-tip="unattributed: ${fmtK(p.unattributed)} — no file
                on disk predicts this" style="width:${w(p.unattributed)};
                background:${HATCH};border-radius:2px"></span>
            </span></span>
        </div>
        <div class="lInv" style="display:none;padding:2px 0 18px 38px">
          <div class="kicker" style="padding:10px 0 6px">This project's files
            · ${fmtK(p.itemized)}</div>
          ${p.items.length ? invTable(p.items, "background:#2F3437;opacity:.8",
                                      maxTok)
            : `<div style="color:var(--muted);font-size:12px">nothing
               itemizable — no cwd recorded or no standing files found</div>`}
          <div class="kicker" style="padding:12px 0 6px">Unattributed ·
            ${fmtK(p.unattributed)}</div>
          ${invTable([{name: "unattributed", tokens: p.unattributed,
            note: "Suspects: SessionStart hook output, MCP server instructions,"
                  + " mid-session injections", tag: "unknown"}],
            `background:${HATCH}`, maxTok)}
        </div>
      </div>`;
    }).join("");
    el.querySelectorAll("tr.drillable").forEach((r) =>
      r.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const next = r.nextElementSibling;
        const open = next.style.display !== "none";
        next.style.display = open ? "none" : "table-row";
        r.querySelector(".ichev").textContent = open ? "▸" : "▾";
      }));
    el.querySelectorAll(".lHead").forEach((h) =>
      h.addEventListener("click", (ev) => {
        if (ev.target.closest("[data-tip]") &&
            ev.target.closest(".chev") === null &&
            ev.target.classList.contains("num")) return;
        const inv = h.nextElementSibling;
        const open = inv.style.display !== "none";
        inv.style.display = open ? "none" : "block";
        h.querySelector(".chev").textContent = open ? "▸" : "▾";
      }));
    bindTips(el);
  }

  window.renderLedger = render;
})();
