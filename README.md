# Sky Sync AI — Fleet Readiness System (Frontend Demo)

A real-time maintenance and readiness system for a helicopter fleet. It runs **fully offline** on a local network, with a live dashboard for commanders, workflows for the control tower, engineers and pilots, and an AI maintenance assistant.

This repository contains the **frontend only**, packaged as a clickable demo with fictional sample data.
The production backend is private and **not** included.

![Command Dashboard](docs/screenshots/command-dashboard.png)

## ▶️ Try it

**Live demo:** _coming soon (GitHub Pages)_

Or run it locally with no installs and no build step:

```bash
git clone https://github.com/salemyousry4-design/skysync-ai-demo.git
cd skysync-ai-demo
python -m http.server 8000
# open http://localhost:8000
```

On the sign-in screen, pick a role (or sign in with any demo username and the password `demo`).
**Tip:** open two roles in two browser tabs, for example *Tower* and *Commander*. Clear a takeoff in one tab and watch the other one update live.

## 👥 One system, six roles

| Role | What they do |
|---|---|
| **Commander** | Fleet readiness at a glance: mission-ready %, health trend, predictive alerts |
| **Tower Operator** | Clear takeoffs and record landings (overdue aircraft are blocked automatically) |
| **Maintenance Engineer** | Open work orders, record the work that was done |
| **Chief Engineer** | Review completed work and certify aircraft airworthy, or send it back for rework |
| **Pilot** | Pre-flight briefing for any aircraft, report defects after landing |
| **System Administrator** | Users and roles, 2FA, account lockout, security log, append-only activity log |

## ✨ Highlights

- **Live sync across stations.** Every screen updates the moment someone acts (WebSocket in production).
- **Explainable health score.** Every aircraft gets a 0–100 score with the reasons behind it, not just a number.
- **Safety rules enforced by the system.** An overdue aircraft can't be cleared for takeoff, and an aircraft only returns to service after a chief engineer signs it off.
- **AI maintenance assistant.** Answers from the maintenance library and live fleet data, and always cites its sources.
- **Role-based access control.** Each role sees its own screens, and buttons it can't use are disabled.
- **Audit trail.** Every action is logged with who did it and when, and can be exported to CSV.
- **Works on desktop, iPad and phone.** Installable as a home-screen app.
- **Zero dependencies.** Plain HTML, CSS and JavaScript with no frameworks, CDNs or web fonts. It was designed for networks with no internet access.

| | |
|---|---|
| ![Control Tower](docs/screenshots/control-tower.png) | ![AI Assistant](docs/screenshots/ai-assistant.png) |
| ![Reports](docs/screenshots/reports.png) | ![Control Center](docs/screenshots/control-center.png) |

## 🧩 How the demo works

The screens are exactly the ones used in production. They call the same `/api/...` endpoints as before.
In this repo, [`demo.js`](demo.js) stands in for the server: it intercepts those requests and answers them from sample data stored in your browser (`localStorage`). It follows the same business rules as the real backend: status transitions, health scoring and permissions.
Use **Reset demo** at the top of any screen to start over.

The AI assistant in this demo returns pre-written answers. The real system runs a local LLM with retrieval over the maintenance library, fully offline.

## 🏗️ Production architecture (not in this repo)

`Python · FastAPI · SQLite · WebSocket · TOTP two-factor auth · RBAC · local LLM (Ollama) + RAG · Docker`

## ⚠️ Notes

- All aircraft, people and records are **fictional**. Tail numbers such as `SK-101` are made up.
- This demo is for showcasing the UI. It is not a certified maintenance tool, and its answers are not technical guidance.

---

© 2026 · All rights reserved.
