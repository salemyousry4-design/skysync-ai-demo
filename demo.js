// Sky Sync AI — demo bridge.
//
// The screens call /api/... exactly as in production. This file routes those calls
// to the Python engine in skysync_demo/:
//   • if `python server.py` is running → requests go to it over HTTP;
//   • otherwise (GitHub Pages)        → the same Python code runs inside the browser
//                                         with Pyodide, and the data is kept in localStorage.
// All aircraft, people and records are fictional.
"use strict";
(() => {
  const STORE = "skysync.demo.state";
  const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";
  const MODULES = ["__init__", "timeutil", "rules", "permissions", "seed", "assistant", "reports", "api"];
  const DEMO_ACCOUNTS = [
    ["commander", "Commander", "Fleet readiness at a glance"],
    ["tower", "Tower Operator", "Clear takeoffs, record landings"],
    ["engineer", "Maintenance Engineer", "Open and complete work orders"],
    ["chief", "Chief Engineer", "Certify aircraft airworthy"],
    ["pilot", "Pilot", "Pre-flight briefing, report defects"],
    ["admin", "System Administrator", "Users, security, activity log"],
  ];
  const BASE = new URL(".", document.currentScript ? document.currentScript.src : location.href).href;
  const realFetch = window.fetch.bind(window);
  const bc = (() => { try { return new BroadcastChannel("skysync-demo"); } catch { return null; } })();

  // ------------------------------------------------------------------ engine start-up
  const pill = document.createElement("div");
  pill.className = "py-pill";
  const showPill = (text) => { pill.textContent = text; if (!pill.isConnected) document.documentElement.appendChild(pill); };
  const hidePill = () => pill.remove();

  const engine = (async () => {
    const staticHost = location.hostname.endsWith("github.io") || location.protocol === "file:";
    if (!staticHost) {                                       // 1) a local Python server?
      try {
        const r = await realFetch("/api/ping", { cache: "no-store" });
        if (r.ok && (await r.json()).engine === "python") return { mode: "server" };
      } catch {}
    }
    const slow = setTimeout(() => showPill("🐍 Starting the Python engine…"), 250);
    if (!window.loadPyodide) {                               // 2) Python in the browser
      await new Promise((ok, bad) => {
        const s = Object.assign(document.createElement("script"), { src: PYODIDE + "pyodide.js", onload: ok, onerror: bad });
        document.head.appendChild(s);
      });
    }
    const py = await window.loadPyodide({ indexURL: PYODIDE });
    py.FS.mkdirTree("/home/pyodide/skysync_demo");
    await Promise.all(MODULES.map(async (m) => {
      const code = await (await realFetch(`${BASE}skysync_demo/${m}.py`)).text();
      py.FS.writeFile(`/home/pyodide/skysync_demo/${m}.py`, code);
    }));
    py.runPython("import sys; sys.path.insert(0, '/home/pyodide'); from skysync_demo.api import handle_json");
    clearTimeout(slow); hidePill();
    return { mode: "browser", call: py.globals.get("handle_json") };
  })().catch((e) => { console.error(e); showPill("⚠️ Could not start the Python engine — check your connection and reload."); throw e; });

  const readState = () => { try { return JSON.parse(localStorage.getItem(STORE)); } catch { return null; } };
  const writeState = (s) => { try { localStorage.setItem(STORE, JSON.stringify(s)); } catch {} };

  // ------------------------------------------------------------------ fetch → Python
  window.fetch = async (input, init = {}) => {
    const raw = typeof input === "string" ? input : input.url;
    const url = new URL(raw, "http://demo.local");
    if (!url.pathname.startsWith("/api/")) return realFetch(input, init);
    const eng = await engine;
    const method = (init.method || "GET").toUpperCase();
    let res;
    if (eng.mode === "server") {
      res = await realFetch(input, init);
    } else {
      const h = init.headers || {};
      const reply = JSON.parse(eng.call(JSON.stringify({
        method, path: url.pathname.slice(5), query: Object.fromEntries(url.searchParams),
        body: init.body ? JSON.parse(init.body) : {},
        token: String(h.Authorization || h.authorization || "").replace("Bearer ", ""),
        state: readState(),
      })));
      if (method !== "GET" || !readState()) writeState(reply.state);
      res = reply.body && reply.body.__csv !== undefined
        ? new Response(reply.body.__csv, { status: reply.status, headers: { "Content-Type": "text/csv" } })
        : new Response(JSON.stringify(reply.body), { status: reply.status, headers: { "Content-Type": "application/json" } });
    }
    if (method !== "GET" && res.ok && bc) {                  // tell the other tabs
      res.clone().json().then(b => bc.postMessage({ message: b.message })).catch(() => bc.postMessage({}));
    }
    return res;
  };

  // ------------------------------------------------------------------ live sync (stands in for the WebSocket)
  window.connectLive = function (onChange) {
    const me = Session.user;
    const online = [me, { username: "tower", role: "Tower Operator" }, { username: "engineer", role: "Maintenance Engineer" }]
      .filter((u, i, all) => u && all.findIndex(x => x.username === u.username) === i);
    const box = document.getElementById("online");
    if (box) box.innerHTML = `Online now (${online.length})<br>` + online.map(u => `<span title="${esc(u.role)}">${esc(u.username)}</span>`).join("");
    let timer = null, rev = null;
    const refresh = () => { clearTimeout(timer); timer = setTimeout(() => onChange({}), 150); };
    if (bc) bc.addEventListener("message", (e) => { if (e.data?.message) toast(e.data.message); refresh(); });
    engine.then((eng) => {
      document.getElementById("live-dot")?.classList.add("on");
      const t = document.getElementById("live-text");
      if (t) t.textContent = eng.mode === "server" ? "Connected" : "Connected (demo)";
      if (eng.mode === "server") {                           // other devices: watch the change counter
        setInterval(async () => {
          try {
            const r = await (await realFetch("/api/ping", { cache: "no-store" })).json();
            if (rev !== null && r.rev !== rev) refresh();
            rev = r.rev;
          } catch {}
        }, 2500);
      }
    }).catch(() => {});
  };

  window.showPhoneQr = function (url) {
    modal(`<div style="text-align:center"><h3 style="margin-top:0">Open Sky Sync on a phone</h3>
      <p class="muted">In the real system, phones and iPads on the <b>same local Wi-Fi</b> scan a QR code here
      and open <b>${esc(url)}</b> — no internet needed.<br><br>In this demo, run <code>python server.py</code> and open
      your computer's address on the phone, or just open this page's link.</p>
      <button class="btn gray" onclick="closeModal()">Close</button></div>`);
  };

  // ------------------------------------------------------------------ demo banner & role picker
  const css = document.createElement("style");
  css.textContent = `
    .py-pill{position:fixed;right:16px;bottom:16px;z-index:99;padding:10px 16px;border-radius:99px;font:600 13px system-ui,sans-serif;
      background:#0e1f3d;color:#cfe0ff;border:1px solid #2f7cf6;box-shadow:0 6px 24px #0008}
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

  async function resetDemo(e) {
    e.preventDefault();
    if (!confirm("Reset all demo data to the starting point?")) return;
    try { await api("/api/demo/reset", { method: "POST" }); } catch {}
    location.reload();
  }

  const origShell = window.renderShell;
  window.renderShell = function (...args) {
    const page = origShell(...args);
    if (page) {
      const bar = document.createElement("div");
      bar.className = "demo-bar";
      bar.innerHTML = `<span><b>Live demo</b> — fictional sample data · runs on a Python engine · the production backend is private.</span>
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
    box.innerHTML = `<h3>Try the live demo</h3>
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
  if (offline) offline.innerHTML = "🔒 Real system: local network only, no internet.";
})();
