// Sky Sync AI — online demo mode.
//
// The real system runs on a private FastAPI server inside a local network (no internet).
// That backend is NOT part of this repository. For the public demo, this file stands in
// for it: it answers the same /api/... requests the screens make, using sample data kept
// in your own browser (localStorage). Nothing is sent anywhere.
//
// All aircraft, people and records here are fictional.
"use strict";
(() => {
  const STORE = "skysync.demo.v1";
  const DAY = 864e5, HOUR = 36e5, MIN = 6e4;
  const now = () => Date.now();
  const iso = (t) => new Date(t).toISOString().slice(0, 19);
  const P = (s) => (s ? Date.parse(s.endsWith("Z") ? s : s + "Z") : null);
  const r1 = (n) => Math.round(n * 10) / 10;
  const MAINT = new Set(["REPAIR", "PART_REPLACEMENT"]);
  const TYPE_LABEL = { INSPECTION: "Inspection", ROUTINE: "Routine check", REPAIR: "Repair", PART_REPLACEMENT: "Part replacement" };

  // ------------------------------------------------------------------ roles & permissions
  const ROLES = ["System Administrator", "Commander", "Tower Operator", "Chief Engineer",
                 "Maintenance Manager", "Maintenance Engineer", "Pilot"];
  const BASE = ["dashboard.view", "workorders.view", "assistant.use"];
  const PERMS = {
    "System Administrator": [...BASE, "workorders.create", "workorders.complete", "workorders.signoff", "flight.operate",
                             "defects.report", "preflight.acknowledge", "fleet.manage", "reports.view"],
    "Commander": [...BASE, "reports.view"],
    "Tower Operator": ["dashboard.view", "workorders.view", "flight.operate"],
    "Chief Engineer": [...BASE, "workorders.create", "workorders.complete", "workorders.signoff", "fleet.manage", "reports.view"],
    "Maintenance Manager": [...BASE, "workorders.create", "workorders.complete", "reports.view"],
    "Maintenance Engineer": [...BASE, "workorders.create", "workorders.complete"],
    "Pilot": [...BASE, "defects.report", "preflight.acknowledge"],
  };
  const DEMO_ACCOUNTS = [
    ["commander", "Commander", "Fleet readiness at a glance"],
    ["tower", "Tower Operator", "Clear takeoffs, record landings"],
    ["engineer", "Maintenance Engineer", "Open and complete work orders"],
    ["chief", "Chief Engineer", "Certify aircraft airworthy"],
    ["pilot", "Pilot", "Pre-flight briefing, report defects"],
    ["admin", "System Administrator", "Users, security, activity log"],
  ];

  // ------------------------------------------------------------------ sample data
  function rng(seed) { return () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; }; }

  function seed() {
    const t = now(), r = rng(7);
    const ac = (id, o) => ({ aircraft_id: id, model: "AH-64D", notes: "", ops_status: "AVAILABLE", ...o });
    const aircraft = [
      ac("SK-101", { total_flight_hours: 1243.5, hours_since_maintenance: 12.4, last_maintenance_at: iso(t - 9 * DAY), next_due_at: iso(t + 21 * DAY) }),
      ac("SK-102", { ops_status: "AIRBORNE", total_flight_hours: 987.2, hours_since_maintenance: 31.0, last_maintenance_at: iso(t - 18 * DAY), next_due_at: iso(t + 12 * DAY) }),
      ac("SK-103", { total_flight_hours: 1508.9, hours_since_maintenance: 44.2, last_maintenance_at: iso(t - 26 * DAY), next_due_at: iso(t + 4 * DAY) }),
      ac("SK-104", { total_flight_hours: 765.0, hours_since_maintenance: 47.1, last_maintenance_at: iso(t - 29 * DAY), next_due_at: iso(t + 1 * DAY) }),
      ac("SK-105", { total_flight_hours: 1120.3, hours_since_maintenance: 51.6, last_maintenance_at: iso(t - 32 * DAY), next_due_at: iso(t - 2 * DAY) }),
      ac("SK-106", { total_flight_hours: 402.7, hours_since_maintenance: 3.5, last_maintenance_at: iso(t - 2 * DAY), next_due_at: iso(t + 28 * DAY) }),
    ];

    let id = 100;
    const wo = (a, type, title, o) => ({ work_order_id: ++id, aircraft_id: a, type, title, description: "", part_name: null,
      status: "CLOSED", opened_at: null, opened_by_name: "engineer", completed_at: null, completed_by_name: null,
      completion_notes: null, signed_at: null, signed_by_name: null, signoff_notes: null, ...o });
    const closed = (a, type, title, daysAgo, notes, part) => wo(a, type, title, { part_name: part || null,
      opened_at: iso(t - daysAgo * DAY), completed_at: iso(t - daysAgo * DAY + 20 * HOUR), completed_by_name: "engineer",
      completion_notes: notes, signed_at: iso(t - daysAgo * DAY + 26 * HOUR), signed_by_name: "chief" });
    const work_orders = [
      closed("SK-104", "ROUTINE", "Main rotor blade tracking", 40, "Tracking within limits."),
      closed("SK-105", "INSPECTION", "30-day calendar inspection", 33, "Inspection complete, no findings."),
      closed("SK-103", "REPAIR", "Hydraulic fitting leak — utility system", 22, "Fitting re-torqued, leak check passed."),
      closed("SK-102", "ROUTINE", "Post-flight check", 19, "Completed, no defects."),
      closed("SK-101", "PART_REPLACEMENT", "Fuel control unit replacement", 10, "Unit replaced, engine ground run OK.", "Fuel Control Unit"),
      closed("SK-106", "INSPECTION", "50-hour phased inspection", 3, "All items inspected, no findings."),
      wo("SK-104", "INSPECTION", "50-hour phased inspection", { status: "AWAITING_SIGNOFF", opened_at: iso(t - 30 * HOUR),
        completed_at: iso(t - 3 * HOUR), completed_by_name: "engineer",
        completion_notes: "Phase inspection complete. Minor chafing on a cable clamp corrected." }),
      wo("SK-103", "REPAIR", "Tail rotor gearbox chip light", { status: "OPEN", part_name: "TGB chip detector",
        description: "Chip light illuminated after landing. Inspect detector and gearbox oil.", opened_at: iso(t - 6 * HOUR) }),
    ];

    const flights = [];
    for (const a of aircraft) {
      for (let d = 89; d >= 1; d--) {
        if (r() < 0.33) {
          const off = t - d * DAY + (8 + Math.floor(r() * 6)) * HOUR, h = r1(1 + r() * 2);
          flights.push({ aircraft_id: a.aircraft_id, takeoff_at: iso(off), landed_at: iso(off + h * HOUR), hours: h });
        }
      }
    }
    flights.push({ aircraft_id: "SK-102", takeoff_at: iso(t - 50 * MIN), landed_at: null, hours: null });

    const log = [];
    const L = (minsAgo, kind, message, username, aircraft_id = null) =>
      log.push({ kind, message, username, aircraft_id, created_at: iso(t - minsAgo * MIN) });
    for (const f of flights.filter(f => f.landed_at && P(f.takeoff_at) > t - 3 * DAY)) {
      log.push({ kind: "TAKEOFF", message: `${f.aircraft_id} – cleared for takeoff`, username: "tower", aircraft_id: f.aircraft_id, created_at: f.takeoff_at });
      log.push({ kind: "LANDED", message: `${f.aircraft_id} – landed after ${f.hours.toFixed(1)}h`, username: "tower", aircraft_id: f.aircraft_id, created_at: f.landed_at });
    }
    L(2 * 1440 + 200, "AIRWORTHY", "SK-106 – certified airworthy ✔", "chief", "SK-106");
    L(1800, "WO_OPENED", "SK-104 – Inspection (50-hour phased inspection)", "engineer", "SK-104");
    L(400, "SEC_LOGIN_FAILED", "Failed sign-in for 'enginer' (unknown user)", "enginer");
    L(362, "DEFECT_REPORTED", "SK-103 – pilot reported: chip light after landing", "pilot", "SK-103");
    L(360, "WO_OPENED", "SK-103 – Repair (Tail rotor gearbox chip light)", "engineer", "SK-103");
    L(240, "AI_QUESTION", "Asked: TGB chip light after landing — what do I do?", "engineer");
    L(180, "WO_COMPLETED", "SK-104 – work done, awaiting sign-off (50-hour phased inspection)", "engineer", "SK-104");
    L(95, "PREFLIGHT_ACK", "SK-101 – pre-flight review acknowledged", "pilot", "SK-101");
    L(52, "SEC_LOGIN_OK", "tower signed in", "tower");
    L(50, "TAKEOFF", "SK-102 – cleared for takeoff", "tower", "SK-102");

    const trend = [];
    for (let d = 29; d >= 0; d--) {
      const day = new Date(t - d * DAY); day.setUTCHours(0, 0, 0, 0);
      trend.push({ day: iso(day.getTime()), fleet_health: Math.round(84 + 5 * Math.sin(d / 4) + (r() - 0.5) * 4) });
    }

    const users = DEMO_ACCOUNTS.map(([username, role]) => ({ username, role, active: true, locked: false,
      two_factor: username === "admin", must_change_password: false }));
    users.push({ username: "engineer2", role: "Maintenance Engineer", active: true, locked: true, two_factor: false, must_change_password: false });
    users.push({ username: "pilot2", role: "Pilot", active: false, locked: false, two_factor: false, must_change_password: false });

    return { v: 1, aircraft, work_orders, flights, log, trend, users, ai: [], require_2fa: false, next_wo: id + 1 };
  }

  // ------------------------------------------------------------------ storage
  let S = null;
  function load() {
    try { S = JSON.parse(localStorage.getItem(STORE)); } catch { S = S || null; }
    if (!S || S.v !== 1) { S = seed(); S.aircraft.forEach(a => recompute(a.aircraft_id)); save(); }
  }
  function save() { try { localStorage.setItem(STORE, JSON.stringify(S)); } catch {} }
  const bc = (() => { try { return new BroadcastChannel("skysync-demo"); } catch { return null; } })();

  function log(kind, message, user, aircraft_id = null) {
    const e = { kind, message, username: user ? user.username : "system", aircraft_id, created_at: iso(now()) };
    S.log.push(e);
    if (bc && !kind.startsWith("SEC_") && !kind.startsWith("AI_")) bc.postMessage({ message });
    return e;
  }

  // ------------------------------------------------------------------ domain rules (same as the real server)
  const find = (id) => S.aircraft.find(a => a.aircraft_id === id) || fail(404, `Aircraft ${id} not found`);
  const wosOf = (id) => S.work_orders.filter(w => w.aircraft_id === id);
  const isOverdue = (a) => a.hours_since_maintenance >= 50 || (a.next_due_at && P(a.next_due_at) < now());
  const riskLevel = (s) => (s >= 90 ? "Low" : s >= 75 ? "Medium" : "High");

  function health(a, wos) {
    let score = 100; const reasons = [];
    const usage = a.hours_since_maintenance / 50;
    if (usage > 0.2) { const p = Math.min(30, usage * 25); score -= p; reasons.push(`${a.hours_since_maintenance.toFixed(1)}h flown since last maintenance (-${Math.round(p)})`); }
    const defects = wos.filter(w => MAINT.has(w.type) && P(w.opened_at) >= now() - 30 * DAY);
    if (defects.length) { const p = Math.min(20, defects.length * 5); score -= p; reasons.push(`${defects.length} repair/part replacement(s) in last 30 days (-${p})`); }
    if (a.next_due_at) {
      const days = (P(a.next_due_at) - now()) / DAY;
      if (days < 0) { const p = Math.min(30, 10 + Math.abs(days) * 2); score -= p; reasons.push(`Maintenance OVERDUE by ${Math.round(Math.abs(days))} day(s) (-${Math.round(p)})`); }
      else if (days < 3) { score -= 5; reasons.push(`Maintenance due in ${days.toFixed(1)} day(s) (-5)`); }
    }
    const open = wos.filter(w => w.status !== "CLOSED");
    if (open.length) { score -= 8; reasons.push(`${open.length} work order(s) not yet signed off (-8)`); }
    const final = Math.max(0, Math.min(100, Math.round(score)));
    return { score: final, risk: riskLevel(final), reasons };
  }

  function view(a) {
    const wos = wosOf(a.aircraft_id);
    return { ...a, overdue: !!isOverdue(a), health: health(a, wos), open_work_orders: wos.filter(w => w.status !== "CLOSED").length };
  }
  const fleet = () => S.aircraft.map(view);
  const statusKey = (v) => (v.overdue && v.ops_status === "AVAILABLE" ? "GROUNDED" : v.ops_status);

  function recompute(id) {
    const a = find(id);
    if (a.ops_status === "AIRBORNE") return "AIRBORNE";
    const wos = wosOf(id), active = wos.filter(w => w.status === "OPEN");
    a.ops_status = active.length ? (active.some(w => MAINT.has(w.type)) ? "UNDER_MAINTENANCE" : "INSPECTION")
      : wos.some(w => w.status === "AWAITING_SIGNOFF") ? "AWAITING_SIGNOFF" : "AVAILABLE";
    return a.ops_status;
  }

  function insight(fl) {
    const alerts = [];
    for (const a of fl) {
      if (a.overdue) alerts.push({ aircraft_id: a.aircraft_id, level: "critical", text: `${a.aircraft_id}: maintenance overdue — grounded` });
      else if (a.health.risk === "High") alerts.push({ aircraft_id: a.aircraft_id, level: "warning", text: `${a.aircraft_id}: high risk (${a.health.score}%)` });
      else if (a.next_due_at && P(a.next_due_at) - now() < 3 * DAY) alerts.push({ aircraft_id: a.aircraft_id, level: "info", text: `${a.aircraft_id}: check due within 3 days` });
    }
    const week = now() + 7 * DAY;
    const ready = fl.filter(a => ["AVAILABLE", "AIRBORNE"].includes(a.ops_status) && !(a.next_due_at && P(a.next_due_at) < week));
    const scores = fl.map(a => a.health.score);
    const due = fl.map(a => a.next_due_at).filter(Boolean).sort();
    return { ok: !alerts.length, headline: alerts.length ? `${alerts.length} Alert(s) Require Attention` : "All Systems Normal",
      alerts, next_check: due[0] || null, availability_7d: fl.length ? Math.round(100 * ready.length / fl.length) : 0,
      risk_level: riskLevel(scores.reduce((s, x) => s + x, 0) / (scores.length || 1)) };
  }

  const fleetEvents = (limit, aircraft_id) => S.log
    .filter(e => !e.kind.startsWith("SEC_") && !e.kind.startsWith("AI_") && (!aircraft_id || e.aircraft_id === aircraft_id))
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1)).slice(0, limit);

  function report(days) {
    const t = now(), from = t - days * DAY;
    const rows = S.aircraft.map(a => {
      const v = view(a), id = a.aircraft_id;
      const fl = S.flights.filter(f => f.aircraft_id === id && P(f.takeoff_at) >= from);
      const wos = wosOf(id).filter(w => P(w.opened_at) >= from);
      const down = wosOf(id).reduce((s, w) => s + Math.max(0, (w.signed_at ? P(w.signed_at) : t) - Math.max(P(w.opened_at), from)), 0);
      const signed = wos.filter(w => w.signed_at);
      return { aircraft_id: id, status: statusKey(v), health: v.health.score,
        availability_pct: Math.max(0, Math.round(100 * (1 - down / (days * DAY)))),
        sorties: fl.length, flight_hours: r1(fl.reduce((s, f) => s + (f.hours || 0), 0)),
        work_orders: wos.length, defects: wos.filter(w => MAINT.has(w.type)).length,
        avg_turnaround_h: signed.length ? r1(signed.reduce((s, w) => s + (P(w.signed_at) - P(w.opened_at)) / HOUR, 0) / signed.length) : null };
    });
    const sum = (k) => rows.reduce((s, x) => s + x[k], 0);
    return { generated_at: iso(t), days, aircraft: rows, totals: {
      availability_pct: Math.round(sum("availability_pct") / (rows.length || 1)), flight_hours: r1(sum("flight_hours")),
      sorties: sum("sorties"), work_orders: sum("work_orders"), defects: sum("defects") } };
  }

  // ------------------------------------------------------------------ AI assistant (canned answers)
  const LIBRARY = [
    { keys: ["chip", "tgb", "gearbox"], title: "Drive System", section: "Chip detector indications",
      text: "A chip indication means metal particles were collected by the magnetic detector.",
      answer: "1. Treat a chip light as a real indication until proven otherwise [1].\n2. After shutdown, remove and inspect the chip detector: fine fuzz is usually normal wear, flakes or chunks are not [1].\n3. Take an oil sample and check the oil level and filter bypass indicator [2].\n4. If particles exceed limits, open a REPAIR work order and do not release the aircraft until the chief engineer signs it off.\n\nAlways follow the approved technical manual for the exact limits." },
    { keys: ["bounce", "vibration", "track", "blade", "rotor"], title: "Rotor System", section: "Vibration & tracking",
      text: "Vertical bounce after blade work is most often a track or balance issue.",
      answer: "Vertical bounce after a blade change is usually track and balance [1]:\n1. Run a track & balance check with the vibration analysis kit.\n2. Adjust pitch links / trim tabs as the analysis recommends [1].\n3. Re-fly and confirm the readings are within limits before sign-off [2]." },
    { keys: ["hydraulic", "leak", "fitting", "seep"], title: "Hydraulic System", section: "Leak classification",
      text: "Leaks are classified by drops per minute: seep, weep, leak, running leak.",
      answer: "Classify the leak first [1]: count drops per minute after wiping the area clean.\n• Seep / weep: monitor and record.\n• Leak / running leak: open a REPAIR work order before the next flight [2].\nCheck torque on the fitting and the condition of the seal; never over-torque to stop a leak." },
    { keys: ["fuel", "fcu", "engine", "start"], title: "Powerplant", section: "Fuel system troubleshooting",
      text: "Start problems are traced in order: power, fuel, ignition.",
      answer: "Trace engine start problems in order: electrical power → fuel supply → ignition [1].\nCheck fuel filters and the fuel control unit indications, then compare with the troubleshooting table [2]. Record every finding in the work order." },
  ];

  function ask(user, question) {
    const q = question.toLowerCase();
    const m = question.toUpperCase().match(/SK-\d{3}/);
    let answer, sources = [];
    if (m && S.aircraft.some(a => a.aircraft_id === m[0])) {
      const v = view(find(m[0])), open = wosOf(v.aircraft_id).filter(w => w.status !== "CLOSED");
      answer = `${v.aircraft_id} is ${v.ops_status.replaceAll("_", " ").toLowerCase()}${v.overdue ? " and OVERDUE (grounded)" : ""}. Health ${v.health.score}% (risk ${v.health.risk}).\n` +
        (v.health.reasons.length ? "Why: " + v.health.reasons.join("; ") + ".\n" : "") +
        (open.length ? "Open work: " + open.map(w => `${w.title} (${w.status.replaceAll("_", " ").toLowerCase()})`).join(", ") + "." : "No open work orders.") +
        "\n[live fleet data]";
      sources = [{ n: 1, title: "Live fleet data", section: v.aircraft_id, text: "Current status from the database" }];
    } else {
      const hit = LIBRARY.find(d => d.keys.some(k => q.includes(k)));
      if (hit) {
        answer = hit.answer;
        sources = [{ n: 1, title: hit.title, section: hit.section, text: hit.text },
                   { n: 2, title: "General Maintenance Practices", section: "Inspection & sign-off", text: "Every repair is certified by the chief engineer." }];
      } else {
        answer = "I could not find this in the maintenance library, so I will not guess.\nTry asking about a chip light, rotor vibration, a hydraulic leak, an engine start problem — or an aircraft like SK-103.";
      }
    }
    S.ai.push({ username: user.username, question, answer, created_at: iso(now()) });
    log("AI_QUESTION", `Asked: ${question.slice(0, 80)}`, user);
    return { answer, sources, mode: "Demo — canned answers (the real system runs a local LLM + RAG, fully offline)" };
  }

  // ------------------------------------------------------------------ CSV
  const csv = (rows, cols) => [cols.join(","), ...rows.map(r => cols.map(c => `"${String(r[c] ?? "").replaceAll('"', '""')}"`).join(","))].join("\n");

  // ------------------------------------------------------------------ request router
  class HttpError extends Error { constructor(status, message) { super(message); this.status = status; } }
  function fail(status, message) { throw new HttpError(status, message); }
  const need = (user, perm) => {
    if (!user) fail(401, "Please sign in");
    if (!(PERMS[user.role] || []).includes(perm)) fail(403, `Your role (${user.role}) cannot do this`);
  };
  const adminOnly = (user) => { if (!user) fail(401, "Please sign in"); if (user.role !== "System Administrator") fail(403, "System Administrator only"); };
  const userObj = (name) => S.users.find(u => u.username === name) || fail(404, `User ${name} not found`);
  const DEMO_QR = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200"><rect width="200" height="200" fill="#fff"/><rect x="20" y="20" width="160" height="160" fill="none" stroke="#071226" stroke-width="6" stroke-dasharray="12 8"/><text x="100" y="96" text-anchor="middle" font-family="sans-serif" font-size="20" fill="#071226">DEMO</text><text x="100" y="122" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#071226">no real QR code</text></svg>`;

  const routes = [
    // ---- session
    ["POST", /^login$/, (m, q, b) => {
      const u = S.users.find(x => x.username === String(b.username || "").toLowerCase());
      if (!u || (b.password || "") !== (u.password || "demo")) {
        log("SEC_LOGIN_FAILED", `Failed sign-in for '${b.username}'`, { username: b.username || "?" });
        fail(401, "Wrong username or password (demo password: demo)");
      }
      if (u.locked) fail(423, "Account locked after too many failed attempts — ask the administrator");
      if (!u.active) fail(403, "This account is disabled");
      log("SEC_LOGIN_OK", `${u.username} signed in`, u);
      return { session_token: "demo-" + u.username, user: { username: u.username, role: u.role },
               must_change_password: false, two_factor_setup_required: false };
    }],
    ["POST", /^logout$/, (m, q, b, user) => { if (user) log("SEC_LOGOUT", `${user.username} signed out`, user); return { message: "Signed out" }; }],
    ["GET", /^me$/, (m, q, b, user) => { if (!user) fail(401, "Please sign in"); return { ...user, permissions: PERMS[user.role] || [] }; }],
    ["POST", /^account\//, () => fail(400, "Not available in the online demo")],
    ["GET", /^system\/info$/, () => ({ lan_url: "http://skysync.local:8000" })],

    // ---- dashboard & fleet
    ["GET", /^dashboard$/, (m, q, b, user) => {
      need(user, "dashboard.view");
      const fl = fleet(), counts = {};
      for (const a of fl) counts[statusKey(a)] = (counts[statusKey(a)] || 0) + 1;
      const trend = S.trend.slice(0, -1).concat([{ day: S.trend[S.trend.length - 1].day,
        fleet_health: Math.round(fl.reduce((s, a) => s + a.health.score, 0) / (fl.length || 1)) }]);
      return { total: fl.length, counts, trend, aircraft: fl, events: fleetEvents(12), insight: insight(fl) };
    }],
    ["GET", /^fleet$/, (m, q, b, user) => { need(user, "dashboard.view"); return { aircraft: fleet() }; }],
    ["POST", /^fleet$/, (m, q, b, user) => {
      need(user, "fleet.manage");
      const id = String(b.aircraft_id || "").trim().toUpperCase();
      if (!/^[A-Z0-9-]{3,20}$/.test(id)) fail(400, "Aircraft ID: 3–20 letters, digits or dashes");
      if (S.aircraft.some(a => a.aircraft_id === id)) fail(409, `${id} already exists`);
      S.aircraft.push({ aircraft_id: id, model: b.model || "AH-64D", notes: b.notes || "", ops_status: "AVAILABLE",
        total_flight_hours: 0, hours_since_maintenance: 0, last_maintenance_at: null, next_due_at: iso(now() + 30 * DAY) });
      log("AIRCRAFT_ADDED", `${id} added to the fleet`, user, id);
      return { message: `${id} added to the fleet` };
    }],
    ["GET", /^fleet\/([^/]+)$/, (m, q, b, user) => {
      need(user, "dashboard.view");
      const v = view(find(m[1]));
      return { ...v, work_orders: wosOf(v.aircraft_id).sort((a, b) => (a.opened_at < b.opened_at ? 1 : -1)), events: fleetEvents(20, v.aircraft_id) };
    }],
    ["POST", /^fleet\/([^/]+)\/takeoff$/, (m, q, b, user) => {
      need(user, "flight.operate");
      const a = find(m[1]);
      if (a.ops_status !== "AVAILABLE") fail(409, `${a.aircraft_id} is ${a.ops_status} — not cleared for takeoff`);
      if (isOverdue(a)) fail(409, `${a.aircraft_id} is overdue for maintenance — GROUNDED`);
      a.ops_status = "AIRBORNE";
      S.flights.push({ aircraft_id: a.aircraft_id, takeoff_at: iso(now()), landed_at: null, hours: null });
      log("TAKEOFF", `${a.aircraft_id} – cleared for takeoff`, user, a.aircraft_id);
      return { message: `${a.aircraft_id} cleared for takeoff` };
    }],
    ["POST", /^fleet\/([^/]+)\/land$/, (m, q, b, user) => {
      need(user, "flight.operate");
      const a = find(m[1]), h = Number(b.flight_hours);
      if (!(h > 0 && h <= 12)) fail(400, "flight_hours must be between 0 and 12");
      if (a.ops_status !== "AIRBORNE") fail(409, `${a.aircraft_id} is not airborne`);
      const f = S.flights.filter(x => x.aircraft_id === a.aircraft_id && !x.landed_at).pop();
      if (f) { f.landed_at = iso(now()); f.hours = h; }
      a.ops_status = "AVAILABLE"; a.total_flight_hours = r1(a.total_flight_hours + h); a.hours_since_maintenance = r1(a.hours_since_maintenance + h);
      log("LANDED", `${a.aircraft_id} – landed after ${h.toFixed(1)}h`, user, a.aircraft_id);
      return { message: `${a.aircraft_id} landed — ${h.toFixed(1)}h recorded` };
    }],
    ["POST", /^fleet\/([^/]+)\/work-orders$/, (m, q, b, user) => {
      need(user, "workorders.create");
      const a = find(m[1]);
      if (a.ops_status === "AIRBORNE") fail(409, `${a.aircraft_id} is airborne — cannot open a work order`);
      if (!TYPE_LABEL[b.type]) fail(400, "Unknown work order type");
      if (!b.title || b.title.trim().length < 3) fail(400, "title: give the work order a title");
      S.work_orders.push({ work_order_id: S.next_wo++, aircraft_id: a.aircraft_id, type: b.type, title: b.title.trim(),
        description: b.description || "", part_name: b.part_name || null, status: "OPEN", opened_at: iso(now()),
        opened_by_name: user.username, completed_at: null, completed_by_name: null, completion_notes: null,
        signed_at: null, signed_by_name: null, signoff_notes: null });
      recompute(a.aircraft_id);
      log("WO_OPENED", `${a.aircraft_id} – ${TYPE_LABEL[b.type]} (${b.title.trim()})`, user, a.aircraft_id);
      return { message: "Work order opened" };
    }],
    ["POST", /^fleet\/([^/]+)\/preflight-ack$/, (m, q, b, user) => {
      need(user, "preflight.acknowledge");
      const a = find(m[1]);
      if (a.ops_status !== "AVAILABLE") fail(409, `${a.aircraft_id} is ${a.ops_status} — not ready for flight`);
      log("PREFLIGHT_ACK", `${a.aircraft_id} – pre-flight review acknowledged`, user, a.aircraft_id);
      return { message: "Pre-flight review recorded" };
    }],
    ["POST", /^fleet\/([^/]+)\/defects$/, (m, q, b, user) => {
      need(user, "defects.report");
      const a = find(m[1]), d = String(b.description || "").trim();
      if (d.length < 5) fail(400, "describe the defect (at least 5 characters)");
      if (a.ops_status === "AIRBORNE") fail(409, "Report the defect after landing");
      S.work_orders.push({ work_order_id: S.next_wo++, aircraft_id: a.aircraft_id, type: "INSPECTION", title: "Pilot defect report",
        description: d, part_name: null, status: "OPEN", opened_at: iso(now()), opened_by_name: user.username, completed_at: null,
        completed_by_name: null, completion_notes: null, signed_at: null, signed_by_name: null, signoff_notes: null });
      recompute(a.aircraft_id);
      log("DEFECT_REPORTED", `${a.aircraft_id} – pilot reported: ${d.slice(0, 80)}`, user, a.aircraft_id);
      return { message: "Defect reported — the workshop has been notified" };
    }],
    ["GET", /^components\/aircraft\/([^/]+)$/, (m) => {
      const id = find(m[1]).aircraft_id;
      const parts = [["Engine No.1", "ENG1"], ["Engine No.2", "ENG2"], ["Main transmission", "MXMSN"], ["Intermediate gearbox", "IGB"],
                     ["Tail rotor gearbox", "TGB"], ["Main rotor blade set", "MRB"], ["Auxiliary power unit", "APU"]];
      return { components: parts.map(([n, c]) => ({ component_name: n, component_id: `${id}-${c}`, notes: "" })) };
    }],

    // ---- work orders & records
    ["GET", /^work-orders$/, (m, q, b, user) => {
      need(user, "workorders.view");
      return { work_orders: S.work_orders.filter(w => !q.status || w.status === q.status).sort((a, b) => (a.opened_at < b.opened_at ? 1 : -1)) };
    }],
    ["POST", /^work-orders\/(\d+)\/complete$/, (m, q, b, user) => {
      need(user, "workorders.complete");
      const w = S.work_orders.find(x => x.work_order_id === +m[1]) || fail(404, "Work order not found");
      if (w.status !== "OPEN") fail(409, "Only OPEN work orders can be completed");
      if (!b.notes || b.notes.trim().length < 3) fail(400, "Describe what was done");
      Object.assign(w, { status: "AWAITING_SIGNOFF", completed_by_name: user.username, completed_at: iso(now()), completion_notes: b.notes.trim() });
      recompute(w.aircraft_id);
      log("WO_COMPLETED", `${w.aircraft_id} – work done, awaiting sign-off (${w.title})`, user, w.aircraft_id);
      return { message: "Submitted for sign-off" };
    }],
    ["POST", /^work-orders\/(\d+)\/sign-off$/, (m, q, b, user) => {
      need(user, "workorders.signoff");
      const w = S.work_orders.find(x => x.work_order_id === +m[1]) || fail(404, "Work order not found");
      if (w.status !== "AWAITING_SIGNOFF") fail(409, "Work order is not awaiting sign-off");
      if (b.approve) {
        Object.assign(w, { status: "CLOSED", signed_by_name: user.username, signed_at: iso(now()), signoff_notes: b.notes || "" });
        if (recompute(w.aircraft_id) === "AVAILABLE") {
          Object.assign(find(w.aircraft_id), { hours_since_maintenance: 0, last_maintenance_at: iso(now()), next_due_at: iso(now() + 30 * DAY) });
          log("AIRWORTHY", `${w.aircraft_id} – certified airworthy ✔`, user, w.aircraft_id);
          return { message: `${w.aircraft_id} certified airworthy` };
        }
        log("WO_SIGNED", `${w.aircraft_id} – work order signed (${w.title})`, user, w.aircraft_id);
        return { message: "Work order signed" };
      }
      Object.assign(w, { status: "OPEN", completed_by_name: null, completed_at: null, signoff_notes: b.notes || "" });
      recompute(w.aircraft_id);
      log("WO_REJECTED", `${w.aircraft_id} – sign-off rejected: ${b.notes || "rework required"}`, user, w.aircraft_id);
      return { message: "Sent back for rework" };
    }],
    ["GET", /^records(\.csv)?$/, (m, q, b, user) => {
      need(user, "workorders.view");
      const s = (q.q || "").toLowerCase();
      const rows = S.work_orders.filter(w => (!q.aircraft_id || w.aircraft_id === q.aircraft_id) && (!q.status || w.status === q.status)
        && (!q.type || w.type === q.type)
        && (!s || [w.title, w.part_name, w.description, w.completion_notes].some(x => (x || "").toLowerCase().includes(s))))
        .sort((a, b) => (a.opened_at < b.opened_at ? 1 : -1));
      return m[1] ? { __csv: csv(rows, ["opened_at", "aircraft_id", "type", "title", "part_name", "status", "opened_by_name", "completed_by_name", "completion_notes", "signed_by_name", "signed_at"]) }
                  : { records: rows };
    }],
    ["GET", /^reports\/fleet(\.csv)?$/, (m, q, b, user) => {
      need(user, "dashboard.view");
      const r = report(+q.days || 30);
      return m[1] ? { __csv: csv(r.aircraft, Object.keys(r.aircraft[0] || {})) } : r;
    }],

    // ---- AI assistant
    ["POST", /^assistant\/ask$/, (m, q, b, user) => { need(user, "assistant.use"); if (!b.question?.trim()) fail(400, "Type a question"); return ask(user, b.question.trim()); }],
    ["GET", /^assistant\/history$/, (m, q, b, user) => {
      need(user, "assistant.use");
      return { history: S.ai.filter(x => x.username === user.username).slice(-(+q.limit || 10)).reverse() };
    }],
    ["GET", /^assistant\/status$/, () => ({ documents: LIBRARY.length + 1, chunks: 38, llm_model: "none online (demo answers)" })],

    // ---- administrator
    ["GET", /^admin\/activity(\.csv)?$/, (m, q, b, user) => {
      adminOnly(user);
      const from = now() - (+q.days || 30) * DAY, s = (q.q || "").toLowerCase();
      const inPeriod = S.log.filter(e => P(e.created_at) >= from);
      const matched = inPeriod.filter(e => (!q.user || e.username === q.user) && (!q.kind || e.kind.startsWith(q.kind))
        && (!s || [e.message, e.username, e.aircraft_id].some(x => (x || "").toLowerCase().includes(s))))
        .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
      if (m[1]) return { __csv: csv(matched, ["created_at", "username", "kind", "aircraft_id", "message"]) };
      const group = (k) => Object.entries(inPeriod.reduce((o, e) => ((o[e[k]] = (o[e[k]] || 0) + 1), o), {}))
        .map(([key, count]) => ({ [k]: key, count })).sort((a, b) => b.count - a.count);
      const today = new Date(); today.setHours(0, 0, 0, 0);
      return { total_actions: S.log.length, today: S.log.filter(e => P(e.created_at) >= today.getTime()).length,
        matched: matched.length, ai_questions: S.ai.length + 1, by_user: group("username"), by_kind: group("kind"), events: matched.slice(0, 200) };
    }],
    ["GET", /^admin\/overview$/, (m, q, b, user) => {
      adminOnly(user);
      return { online: [{ username: user.username, role: user.role, ip: "10.0.0.5" }, { username: "tower", role: "Tower Operator", ip: "10.0.0.21" },
                        { username: "engineer", role: "Maintenance Engineer", ip: "10.0.0.34" }],
        require_2fa: S.require_2fa, two_factor_exempt: DEMO_ACCOUNTS.map(a => a[0]), roles: ROLES,
        users: S.users.map(({ password, ...u }) => u),
        security_log: S.log.filter(e => e.kind.startsWith("SEC_")).sort((a, b) => (a.created_at < b.created_at ? 1 : -1)).slice(0, 30) };
    }],
    ["PUT", /^admin\/policy$/, (m, q, b, user) => {
      adminOnly(user); S.require_2fa = !!b.require_2fa;
      log("SEC_POLICY", `Mandatory 2FA ${S.require_2fa ? "enabled" : "disabled"}`, user);
      return { message: S.require_2fa ? "Two-factor sign-in is now mandatory (demo accounts are exempt)" : "Two-factor sign-in is optional" };
    }],
    ["POST", /^admin\/backup$/, (m, q, b, user) => { adminOnly(user); log("SEC_BACKUP", "Database backup created", user); return { message: "Backup created (demo — nothing was written)" }; }],
    ["POST", /^admin\/automation\/run$/, (m, q, b, user) => {
      adminOnly(user); const n = insight(fleet()).alerts.length;
      log("AUTO_CHECKS", `Automatic checks ran — ${n} alert(s)`, user);
      return { message: `Checks complete — ${n} alert(s) found` };
    }],
    ["POST", /^admin\/users$/, (m, q, b, user) => {
      adminOnly(user);
      const name = String(b.username || "").trim().toLowerCase();
      if (!/^[a-z0-9._-]{3,30}$/.test(name)) fail(400, "Username: 3–30 letters, digits, . _ -");
      if (S.users.some(u => u.username === name)) fail(409, `${name} already exists`);
      const pw = String(b.password || "");
      if (pw.length < 12 || !/[a-z]/.test(pw) || !/[A-Z]/.test(pw) || !/\d/.test(pw) || !/[^A-Za-z0-9]/.test(pw))
        fail(400, "Password: at least 12 characters with upper- and lowercase letters, a digit and a symbol");
      if (!ROLES.includes(b.role)) fail(400, "Unknown role");
      S.users.push({ username: name, role: b.role, active: true, locked: false, two_factor: false, must_change_password: false, password: pw });
      log("SEC_USER_CREATED", `User ${name} created (${b.role})`, user);
      return { message: `${name} added — they can sign in with that password` };
    }],
    ["PUT", /^admin\/users\/([^/]+)\/status$/, (m, q, b, user) => {
      adminOnly(user); const u = userObj(decodeURIComponent(m[1])); u.active = !!b.active;
      log(u.active ? "SEC_USER_ENABLED" : "SEC_USER_DISABLED", `User ${u.username} ${u.active ? "enabled" : "disabled"}`, user);
      return { message: `${u.username} ${u.active ? "enabled" : "disabled"}` };
    }],
    ["POST", /^admin\/users\/([^/]+)\/unlock$/, (m, q, b, user) => {
      adminOnly(user); const u = userObj(decodeURIComponent(m[1])); u.locked = false;
      log("SEC_USER_UNLOCKED", `User ${u.username} unlocked`, user); return { message: `${u.username} unlocked` };
    }],
    ["POST", /^admin\/users\/([^/]+)\/2fa$/, (m, q, b, user) => {
      adminOnly(user); const u = userObj(decodeURIComponent(m[1])); u.two_factor = true;
      log("SEC_2FA_ENABLED", `Two-factor sign-in enabled for ${u.username}`, user);
      return { qr_svg: DEMO_QR, secret: "DEMO-NOT-A-REAL-SECRET" };
    }],
    ["DELETE", /^admin\/users\/([^/]+)\/2fa$/, (m, q, b, user) => {
      adminOnly(user); const u = userObj(decodeURIComponent(m[1])); u.two_factor = false;
      log("SEC_2FA_RESET", `Two-factor sign-in reset for ${u.username}`, user); return { message: `2FA reset for ${u.username}` };
    }],
    ["POST", /^admin\/users\/([^/]+)\/reset-password$/, (m, q, b, user) => {
      adminOnly(user); const u = userObj(decodeURIComponent(m[1]));
      log("SEC_PASSWORD_RESET", `Password reset for ${u.username}`, user);
      return { temporary_password: "Demo-" + Math.random().toString(36).slice(2, 8) + "!7" };
    }],
  ];

  function handle(method, path, query, body, user) {
    for (const [m, re, fn] of routes) {
      const match = method === m && path.match(re);
      if (match) return fn(match, query, body, user);
    }
    fail(404, `Not available in the demo: ${method} /api/${path}`);
  }

  // ------------------------------------------------------------------ fetch interception
  const realFetch = window.fetch.bind(window);
  const json = (status, data) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
  window.fetch = async (input, init = {}) => {
    const raw = typeof input === "string" ? input : input.url;
    const url = new URL(raw, "http://demo.local");
    if (!url.pathname.startsWith("/api/")) return realFetch(input, init);
    await new Promise(r => setTimeout(r, 80 + Math.random() * 120));   // feels like a network
    load();
    const method = (init.method || "GET").toUpperCase();
    let body = {}; try { body = init.body ? JSON.parse(init.body) : {}; } catch {}
    const h = init.headers || {}, token = String(h.Authorization || h.authorization || "").replace("Bearer ", "");
    const user = token.startsWith("demo-") ? S.users.find(u => u.username === token.slice(5) && u.active) || null : null;
    try {
      const out = handle(method, url.pathname.slice(5), Object.fromEntries(url.searchParams), body, user);
      if (method !== "GET") save();
      if (out && out.__csv !== undefined) return new Response(out.__csv, { status: 200, headers: { "Content-Type": "text/csv" } });
      return json(200, out);
    } catch (e) {
      save();
      if (e instanceof HttpError) return json(e.status, { message: e.message });
      console.error(e);
      return json(500, { message: "Demo error: " + e.message });
    }
  };

  // ------------------------------------------------------------------ live sync between tabs (stands in for the WebSocket)
  window.connectLive = function (onChange) {
    const dot = document.getElementById("live-dot"), txt = document.getElementById("live-text");
    dot?.classList.add("on"); if (txt) txt.textContent = "Connected (demo)";
    const me = Session.user;
    const online = [me, { username: "tower", role: "Tower Operator" }, { username: "engineer", role: "Maintenance Engineer" }]
      .filter((u, i, all) => u && all.findIndex(x => x.username === u.username) === i);
    const box = document.getElementById("online");
    if (box) box.innerHTML = `Online now (${online.length})<br>` + online.map(u => `<span title="${esc(u.role)}">${esc(u.username)}</span>`).join("");
    let timer = null;
    const refresh = () => { clearTimeout(timer); timer = setTimeout(() => onChange({}), 150); };
    if (bc) bc.addEventListener("message", (e) => { if (e.data?.message) toast(e.data.message); refresh(); });
    else window.addEventListener("storage", (e) => { if (e.key === STORE) refresh(); });
  };

  window.showPhoneQr = function (url) {
    modal(`<div style="text-align:center"><h3 style="margin-top:0">Open Sky Sync on a phone</h3>
      <p class="muted">In the real system, phones and iPads on the <b>same local Wi-Fi</b> scan a QR code here
      and open <b>${esc(url)}</b> — no internet needed.<br><br>In this online demo, just open this page's link on your phone.</p>
      <button class="btn gray" onclick="closeModal()">Close</button></div>`);
  };

  // ------------------------------------------------------------------ demo banner & role picker
  const css = document.createElement("style");
  css.textContent = `
    .demo-bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:9px 14px;border-radius:12px;font-size:13px;
      background:#2f7cf61f;border:1px solid #2f7cf655;color:#cfe0ff}
    .demo-bar a{color:var(--cyan);font-weight:600}
    .demo-bar .sp{margin-left:auto;display:flex;gap:14px}
    .demo-roles{margin-top:16px;border-top:1px solid var(--line);padding-top:14px}
    .demo-roles h3{margin:0 0 4px;font-size:15px}
    .demo-roles .grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
    .demo-roles button{text-align:left;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:#102447;color:var(--text)}
    .demo-roles button:hover{border-color:var(--blue);background:#163a75}
    .demo-roles button b{display:block;font-size:14px}.demo-roles button span{font-size:11.5px;color:var(--muted)}
    @media (max-width:420px){.demo-roles .grid2{grid-template-columns:1fr}}`;
  document.head.appendChild(css);

  function resetDemo(e) {
    e.preventDefault();
    if (!confirm("Reset all demo data to the starting point?")) return;
    try { localStorage.removeItem(STORE); } catch {}
    location.reload();
  }

  const origShell = window.renderShell;
  window.renderShell = function (...args) {
    const page = origShell(...args);
    if (page) {
      const bar = document.createElement("div");
      bar.className = "demo-bar";
      bar.innerHTML = `🧪 <span><b>Live demo</b> — fictional sample data, stored only in your browser. The backend is private.</span>
        <span class="sp"><a href="#" id="demo-switch">Switch role</a><a href="#" id="demo-reset">Reset demo</a></span>`;
      document.querySelector(".main").insertBefore(bar, document.querySelector(".topbar"));
      document.getElementById("demo-switch").onclick = (e) => { e.preventDefault(); Session.clear(); location.href = "index.html"; };
      document.getElementById("demo-reset").onclick = resetDemo;
    }
    return page;
  };

  const signin = document.getElementById("signin");
  if (signin) {
    const box = document.createElement("div");
    box.className = "demo-roles";
    box.innerHTML = `<h3>🧪 Try the live demo</h3>
      <div class="muted" style="font-size:12.5px">Pick a role — or sign in with any username below and password <b>demo</b>.
      Open two roles in two tabs to watch live sync.</div>
      <div class="grid2">${DEMO_ACCOUNTS.map(([u, role, what]) => `<button type="button" data-u="${u}"><b>${role}</b><span>${what}</span></button>`).join("")}</div>`;
    signin.after(box);
    box.querySelectorAll("button[data-u]").forEach(b => b.onclick = () => {
      document.getElementById("u").value = b.dataset.u;
      document.getElementById("p").value = "demo";
      signin.requestSubmit();
    });
  }
  const offline = [...document.querySelectorAll("p.muted")].find(p => p.textContent.includes("Local network only"));
  if (offline) offline.innerHTML = "🔒 Real system: local network only, no internet. This page: an offline-style demo.";
})();
