/* Context ledger tab: measured medians, honest decomposition, inventory. */
"use strict";

(function () {
  const fmtK = (n) => n == null ? "—" : (n / 1000).toFixed(1) + "K";

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
        <td colspan="8" style="padding:14px 0 6px">
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
        <td class="num" data-tip="Full SKILL.md body — loads when the skill
          is invoked" style="font-size:11.5px;text-align:right;width:70px;
          color:var(--sec);border-bottom:1px solid #F7F6F3">${
            s.file_tok ? fmtK(s.file_tok) : "—"} body</td>
        <td class="num" style="font-size:11.5px;text-align:right;width:50px;
          border-bottom:1px solid #F7F6F3">${s.usage ? s.usage.uses : 0}</td>
        <td class="skSpark" data-tip="Click to enlarge with dated axes"
          data-spark="${((s.usage && s.usage.spark) || Array(14).fill(0))
            .join(",")}"
          data-sparktok="${((s.usage && s.usage.spark_tok) ||
            Array(14).fill(0)).join(",")}"
          style="text-align:right;width:80px;cursor:pointer;
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
          border-bottom:1px solid #F7F6F3">${it.note}${it.catalog
            ? ` · descriptions ${fmtK(it.catalog)} on use` : ""}${it.full
            ? ` · bodies ${fmtK(it.full)} when invoked` : ""}${it.skills
            ? " · click to drill" : ""}</td>
        <td style="text-align:right;border-bottom:1px solid #F7F6F3">${
          tag(it.tag, it.tag === "prunable" ? "prunable" :
              it.tag === "fixed" ? "fixed cost" : "unknown")}</td>
      </tr>` + (it.skills ? `<tr class="idrill" style="display:none">
        <td colspan="5" style="padding:0">${skillRows(it.skills)}</td>
      </tr>` : "")).join("") + `</table>`;
  }

  async function render(el) {
    el.innerHTML = `<div class="kicker">Context ledger · where context
      comes from</div>
      <h1 style="margin-bottom:2px">What sessions pay before work starts</h1>
      <div style="font-size:12.5px;color:var(--sec)">The
        <span data-tip="Median of each session's first API call context (input +
        cache read + cache create). This is what actually happened — the one
        number that cannot be wrong." style="border-bottom:1px dotted
        var(--muted);cursor:help">measured median</span> is authoritative.
        The tree shows the eager estimate per folder level:
        <span data-tip="Skill, command, and plugin entries cost a small
        calibrated stub eagerly (~25 tok, probes 2026-07-09: a 2,170-token
        description added 46). Their full descriptions are a catalog that
        loads on use — shown as the secondary number."
        style="border-bottom:1px dotted var(--muted);cursor:help">stubs, not
        descriptions</span> — and the
        <span data-tip="The share of a node's measured median that neither
        its branch's files nor stubs predict: hook output, MCP instructions,
        git status, surface differences. Shown, never hidden."
        style="border-bottom:1px dotted var(--muted);cursor:help">unattributed
        share</span> is shown, never hidden.</div>
      <div id="lTree" style="color:var(--muted);margin-top:16px">loading…</div>
      <div style="font-family:var(--mono);font-size:11px;color:var(--muted);
        margin-top:14px">accumulated = the sum down one branch — visiting a
        sibling folder mid-session loads its content on use, not modeled ·
        stub calibration ${""}≈25 tok/entry (measured range 13–46)</div>`;
    bindTips(el);
    const led = await (await fetch("/api/ledger", {cache: "no-store"})).json();
    const th = (txt, align) => `<th style="text-align:${align};
      font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;
      text-transform:uppercase;color:var(--muted);font-weight:500;
      padding:0 0 8px ${align === "right" ? "18px" : "0"};
      border-bottom:1px solid var(--border)">${txt}</th>`;
    el.querySelector("#lTree").innerHTML = `
      <table style="width:100%;border-collapse:collapse"><thead><tr>
        ${th("folder", "left")}
        ${th("additional", "right")}
        ${th("accumulated", "right")}
        ${th("measured median", "right")}
        ${th("unattributed", "right")}
      </tr></thead>
      <tbody>${led.tree.map((nd, i) => {
        const lowN = nd.n != null && nd.n < 3 ? ` <span style="
          font-family:var(--mono);font-size:10px;
          background:var(--tag-yellow-bg);color:var(--tag-yellow);
          border-radius:9999px;padding:1px 7px">N=${nd.n}</span>` : "";
        return `<tr class="lNode" data-i="${i}" style="cursor:pointer">
        <td style="font-family:var(--mono);font-size:12.5px;
          padding:10px 12px 10px ${nd.depth * 26}px;
          border-bottom:1px solid #F2F1EE" data-tip="${nd.path}">
          <span class="chev" style="color:var(--muted);font-size:11px">▸</span>
          ${nd.depth ? "└─ " : ""}${nd.label}${lowN}</td>
        <td class="num" style="text-align:right;font-size:12.5px;
          border-bottom:1px solid #F2F1EE">+${fmtK(nd.additional)}</td>
        <td class="num" style="text-align:right;font-size:13px;font-weight:600;
          border-bottom:1px solid #F2F1EE">${fmtK(nd.accumulated)}</td>
        <td class="num" style="text-align:right;font-size:13px;
          border-bottom:1px solid #F2F1EE">${nd.median != null
            ? fmtK(nd.median) : `<span style="color:var(--muted)">—</span>`}</td>
        <td class="num" style="text-align:right;font-size:12.5px;
          color:var(--sec);border-bottom:1px solid #F2F1EE">${
            nd.unattributed != null ? fmtK(nd.unattributed)
            : `<span style="color:var(--muted)">—</span>`}</td>
      </tr>
      <tr class="lNodeItems" style="display:none"><td colspan="5"
        style="padding:2px 0 16px ${nd.depth * 26 + 22}px">
        ${nd.items.length
          ? invTable(nd.items, "background:#2F3437;opacity:.8",
                     Math.max(...nd.items.map((x) => x.tokens || 0), 1))
          : `<div style="color:var(--muted);font-size:12px">nothing on disk
             at this folder</div>`}
      </td></tr>`; }).join("")}</tbody></table>`;
    el.querySelectorAll("td.skSpark").forEach((c) =>
      c.addEventListener("click", (ev) => {
        ev.stopPropagation();
        window.ccw.sparkZoomRow(c.parentElement,
          {counts: c.dataset.spark.split(",").map(Number),
           tokens: c.dataset.sparktok.split(",").map(Number)}, null, 8);
      }));
    el.querySelectorAll("tr.drillable").forEach((r) =>
      r.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const next = r.nextElementSibling;
        const open = next.style.display !== "none";
        next.style.display = open ? "none" : "table-row";
        r.querySelector(".ichev").textContent = open ? "▸" : "▾";
      }));
    el.querySelectorAll("tr.lNode").forEach((h) =>
      h.addEventListener("click", () => {
        const inv = h.nextElementSibling;
        const open = inv.style.display !== "none";
        inv.style.display = open ? "none" : "table-row";
        h.querySelector(".chev").textContent = open ? "▸" : "▾";
      }));
    bindTips(el);
  }

  window.renderLedger = render;
})();
