// Sky Sync AI — shared code for every screen (no external libraries: air-gapped).
"use strict";

const ROLE_HOME = {
  "Commander": "commander", "System Administrator": "commander",
  "Tower Operator": "tower",
  "Chief Engineer": "chief", "Maintenance Manager": "chief",
  "Maintenance Engineer": "engineer",
  "Pilot": "pilot",
};

const PAGES = [
  { id: "commander", label: "Command Dashboard", icon: "home" },
  { id: "tower", label: "Control Tower", icon: "tower", roles: ["Tower Operator"] },
  { id: "chief", label: "Chief Engineer", icon: "check", roles: ["Chief Engineer", "Maintenance Manager"] },
  { id: "engineer", label: "Workshop", icon: "wrench", roles: ["Maintenance Engineer", "Chief Engineer", "Maintenance Manager"] },
  { id: "pilot", label: "Pilot Briefing", icon: "pilot", roles: ["Pilot"] },
  { id: "records", label: "Maintenance Records", icon: "list" },
  { id: "reports", label: "Analytics & Reports", icon: "chart", roles: ["Chief Engineer", "Maintenance Manager"] },
  { id: "fleet", label: "Aircraft Management", icon: "fleet", only: ["System Administrator", "Chief Engineer"] },
  { id: "assistant", label: "AI Assistant", icon: "ai" },
  { id: "activity", label: "Activity Log", icon: "bolt", only: ["System Administrator"] },
  { id: "control", label: "Control Center", icon: "shield", only: ["System Administrator"] },
];

const ICONS = {
  home: '<path d="M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
  tower: '<path d="M9 22l1-11h4l1 11M7 11h10l-2-5H9zM12 6V2M8 2h8"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
  wrench: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
  pilot: '<circle cx="12" cy="7" r="4"/><path d="M4 21c0-4 4-7 8-7s8 3 8 7"/>',
  ai: '<rect x="4" y="6" width="16" height="12" rx="3"/><path d="M9 11h.01M15 11h.01M9 15h6M12 6V3"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  fleet: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  bulb: '<path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/>',
  shield: '<path d="M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6z"/><path d="M8 12l3 3 5-6"/>',
};
const icon = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;

// ------------------------------------------------------------- background photo
// If the unit placed branding/hero.* on the server, it becomes the background of every screen.
(() => {
  const img = new Image();
  img.onload = () => { document.documentElement.classList.add("has-bg"); document.body?.classList.add("has-hero"); };
  img.src = "brand/hero.svg";
})();

// ------------------------------------------------------------- session
const Session = {
  get token() { try { return localStorage.getItem("skysync.token"); } catch { return null; } },
  get user() { try { return JSON.parse(localStorage.getItem("skysync.user") || "null"); } catch { return null; } },
  save(token, user) { try { localStorage.setItem("skysync.token", token); localStorage.setItem("skysync.user", JSON.stringify(user)); } catch {} },
  clear() { try { localStorage.removeItem("skysync.token"); localStorage.removeItem("skysync.user"); } catch {} },
};

// ------------------------------------------------------------- API
async function api(path, { method = "GET", body } = {}) {
  const headers = { "Accept": "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (Session.token) headers["Authorization"] = "Bearer " + Session.token;
  const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && !path.endsWith("/login") && !path.endsWith("/account/password")) { Session.clear(); location.href = "index.html"; }
  if (res.status === 403 && data.password_change_required) { location.href = "index.html?change=1"; }
  if (res.status === 403 && data.two_factor_setup_required && !path.includes("/account/2fa")) { location.href = "index.html?setup2fa=1"; }
  if (!res.ok) {
    let msg = data.message || data.error || res.statusText;
    if (Array.isArray(data.detail)) msg = data.detail.map(d => `${d.loc.slice(-1)[0]}: ${d.msg}`).join(", ");
    throw new Error(msg);
  }
  return data;
}

// ------------------------------------------------------------- permissions
// Loaded once per screen from /api/me, so buttons a role cannot use are shown disabled.
let PERMISSIONS = new Set();
let permsReady = Promise.resolve();
const can = (permission) => PERMISSIONS.has(permission);
const VIEW_ONLY = (what) => `<div class="view-only">👁 View only — your role cannot ${what}.</div>`;

// ------------------------------------------------------------- formatting
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const toDate = (iso) => iso ? new Date(iso.endsWith("Z") ? iso : iso + "Z") : null;
const fmtDate = (iso) => { const d = toDate(iso); return d ? d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—"; };
const fmtDateTime = (iso) => { const d = toDate(iso); return d ? d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"; };
const STATUS_LABEL = { AVAILABLE: "Available", INSPECTION: "Inspection", UNDER_MAINTENANCE: "Under Maintenance", AWAITING_SIGNOFF: "Awaiting Sign-off", AIRBORNE: "Airborne", GROUNDED: "Grounded (overdue)", OPEN: "Open", CLOSED: "Closed" };
const badge = (s) => `<span class="badge s-${s}">${STATUS_LABEL[s] || s}</span>`;
const healthClass = (n) => n >= 90 ? "h-good" : n >= 75 ? "h-mid" : "h-bad";
const healthColor = (n) => n >= 90 ? "var(--green)" : n >= 75 ? "#facc15" : "var(--red)";
const EVENT_COLOR = { AIRWORTHY: "var(--green)", LANDED: "var(--cyan)", TAKEOFF: "var(--cyan)", WO_OPENED: "var(--orange)", WO_COMPLETED: "#eab308", WO_REJECTED: "var(--red)", WO_SIGNED: "var(--green)", DEFECT_REPORTED: "var(--red)", PREFLIGHT_ACK: "var(--blue)" };
const eventDot = (kind) => `<span class="edot" style="background:${EVENT_COLOR[kind] || "var(--purple)"}"></span>`;

// ------------------------------------------------------------- UI helpers
function toast(msg, kind = "") {
  let box = document.querySelector(".toasts");
  if (!box) { box = document.createElement("div"); box.className = "toasts"; document.body.appendChild(box); }
  const t = document.createElement("div");
  t.className = "toast " + kind; t.textContent = msg; box.appendChild(t);
  setTimeout(() => t.remove(), 5000);
}

function modal(html) {
  let bg = document.querySelector(".modal-bg");
  if (!bg) {
    bg = document.createElement("div"); bg.className = "modal-bg";
    bg.addEventListener("click", e => { if (e.target === bg) closeModal(); });
    document.body.appendChild(bg);
  }
  bg.innerHTML = `<div class="modal">${html}</div>`;
  bg.classList.add("show");
  return bg.querySelector(".modal");
}
function closeModal() { document.querySelector(".modal-bg")?.classList.remove("show"); }

async function run(action, okMsg) {
  try { const r = await action(); toast(okMsg || r?.message || "Done", "ok"); return r; }
  catch (e) { toast(e.message, "err"); return null; }
}

// ------------------------------------------------------------- shell
function renderShell(pageId, title, subtitle) {
  const user = Session.user;
  if (!user || !Session.token) { location.href = "index.html"; return null; }
  const isCmd = ["Commander", "System Administrator"].includes(user.role);
  const nav = PAGES.filter(p => p.only ? p.only.includes(user.role) : (!p.roles || isCmd || p.roles.includes(user.role)))
    .map(p => `<a href="${p.id}.html" class="${p.id === pageId ? "active" : ""}">${icon(p.icon)}${p.label}</a>`).join("");
  document.body.innerHTML = `
  <div class="layout">
    <aside class="sidebar">
      <div class="brand"><img class="side-logo" src="brand/logo.svg" alt="" onerror="this.outerHTML=icon('shield')"><div><b>SKY SYNC AI</b><small>Fleet Readiness System</small></div></div>
      <nav class="nav">${nav}</nav>
      <div class="online" id="online"></div>
      <div class="motto">${icon("shield")}<br>Ready for Mission<br>with Confidence</div>
    </aside>
    <main class="main">
      <div class="topbar">
        <div><h1>${esc(title)}</h1><div class="sub">${esc(subtitle)}</div></div>
        <div class="right">
          <div class="chip secure">${icon("shield")}<div>Offline Mode<b>Air-Gapped</b></div></div>
          <div class="chip"><span class="dot" id="live-dot"></span><div>Live Sync<b id="live-text">Connecting…</b></div></div>
          <div class="chip"><div><span id="clock-date"></span><b id="clock-time"></b></div></div>
          <div class="chip"><div>${esc(user.role)}<b>${esc(user.username)}</b></div></div>
          <button class="btn-ghost" id="logout">Sign out</button>
        </div>
      </div>
      <div id="page" class="grid"></div>
    </main>
  </div>`;
  permsReady = api("/api/me").then(r => { PERMISSIONS = new Set(r.permissions || []); }).catch(() => {});
  document.getElementById("logout").onclick = async () => {
    try { await api("/api/logout", { method: "POST" }); } catch {}
    Session.clear(); location.href = "index.html";
  };
  const tick = () => {
    const d = new Date();
    document.getElementById("clock-date").textContent = d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    document.getElementById("clock-time").textContent = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  };
  tick(); setInterval(tick, 1000 * 15);
  return document.getElementById("page");
}

// ------------------------------------------------------------- live sync (WebSocket)
function connectLive(onChange) {
  let retry = 1000, timer = null;
  const setState = (on, text) => {
    document.getElementById("live-dot")?.classList.toggle("on", on);
    const t = document.getElementById("live-text"); if (t) t.textContent = text;
  };
  const open = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(Session.token)}`);
    ws.onopen = () => { retry = 1000; setState(true, "Connected"); };
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "presence") {
        const box = document.getElementById("online");
        if (box) box.innerHTML = `Online now (${msg.online.length})<br>` +
          msg.online.map(u => `<span title="${esc(u.role)}">${esc(u.username)}</span>`).join("");
        return;
      }
      if (msg.message) toast(msg.message);
      clearTimeout(timer); timer = setTimeout(() => onChange(msg), 150);   // debounce bursts
    };
    ws.onclose = (e) => {
      if (e.code === 4401) { Session.clear(); location.href = "index.html"; return; }
      setState(false, "Reconnecting…");
      setTimeout(open, retry); retry = Math.min(retry * 2, 15000);         // exponential backoff
    };
  };
  open();
}

// ------------------------------------------------------------- aircraft detail (shared)
async function showAircraft(aircraftId) {
  const m = modal(`<p class="muted">Loading ${esc(aircraftId)}…</p>`);
  try {
    const a = await api(`/api/fleet/${encodeURIComponent(aircraftId)}`);
    m.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
        <h3 style="margin:0">${esc(a.aircraft_id)} <span class="muted" style="font-size:14px">${esc(a.model)}</span></h3>
        <button class="btn-ghost" onclick="closeModal()">Close</button>
      </div>
      <p>${badge(a.ops_status)} &nbsp; Health <b class="${healthClass(a.health.score)}">${a.health.score}%</b>
         &nbsp; Risk <b>${a.health.risk}</b> ${a.overdue ? '&nbsp; <span class="overdue">OVERDUE — GROUNDED</span>' : ""}</p>
      ${a.health.reasons.length ? `<ul class="reasons">${a.health.reasons.map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : '<p class="muted">No health deductions.</p>'}
      <div class="card" style="margin-top:12px"><div class="meta">
        <div>Total hours: <b>${a.total_flight_hours.toFixed(1)}</b></div>
        <div>Since maintenance: <b>${a.hours_since_maintenance.toFixed(1)}h</b></div>
        <div>Last maintenance: <b>${fmtDate(a.last_maintenance_at)}</b></div>
        <div>Next due: <b class="${a.overdue ? "overdue" : ""}">${fmtDate(a.next_due_at)}</b></div>
      </div></div>
      <h3 style="margin-top:16px">Work orders</h3>
      ${a.work_orders.length ? `<table><tr><th>Opened</th><th>Type</th><th>Title</th><th>Status</th><th>By</th></tr>
        ${a.work_orders.map(w => `<tr><td>${fmtDate(w.opened_at)}</td><td>${esc(w.type)}</td>
          <td>${esc(w.title)}${w.part_name ? ` <span class="muted">(${esc(w.part_name)})</span>` : ""}
          ${w.completion_notes ? `<div class="muted">✔ ${esc(w.completion_notes)}</div>` : ""}</td>
          <td>${badge(w.status)}</td><td>${esc(w.opened_by_name || "")}${w.signed_by_name ? ` → ${esc(w.signed_by_name)}` : ""}</td></tr>`).join("")}
        </table>` : '<p class="empty">No work orders.</p>'}
      <h3 style="margin-top:16px">History</h3>
      <ul class="events">${a.events.map(e => `<li>${eventDot(e.kind)}<div>${esc(e.message)}</div><span class="t">${fmtDateTime(e.created_at)}</span></li>`).join("") || '<li class="empty">No events.</li>'}</ul>`;
  } catch (e) { m.innerHTML = `<p class="overdue">${esc(e.message)}</p><button class="btn gray" onclick="closeModal()">Close</button>`; }
}

// QR code to open the system on a phone (same Wi-Fi network)
function showPhoneQr(url) {
  modal(`<div style="text-align:center">
    <h3 style="margin-top:0">Open Sky Sync on your phone</h3>
    <img src="/api/system/qr.svg" alt="QR code" style="width:240px;height:240px;border-radius:12px;background:#fff">
    <p style="font-size:20px;margin:12px 0"><b>${esc(url)}</b></p>
    <p class="muted">1. Connect the phone to the <b>same Wi-Fi</b> as this computer.<br>
      2. Scan the code with the camera.<br>
      3. Add to Home Screen — iPhone: Share ▸ Add to Home Screen · Android: ⋮ ▸ Add to Home screen.</p>
    <button class="btn gray" onclick="closeModal()">Close</button></div>`);
}

// CSV export: fetched with the login token, then saved as a file
async function downloadCsv(path, filename) {
  try {
    const res = await fetch(path, { headers: { "Authorization": "Bearer " + Session.token } });
    if (!res.ok) throw new Error("Export failed (" + res.status + ")");
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: filename });
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    toast("Exported " + filename, "ok");
  } catch (e) { toast(e.message, "err"); }
}

function healthBar(score) {
  return `<div class="bar"><i style="width:${score}%;background:${healthColor(score)}"></i></div>`;
}
