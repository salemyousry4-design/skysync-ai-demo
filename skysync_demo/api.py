"""
The demo API — the same ``/api/...`` endpoints and JSON shapes as the production
server, implemented over a plain ``dict`` state.

Two front doors use it:

* ``server.py`` — a real HTTP server (standard library only);
* ``handle_json()`` — called from the browser through Pyodide, so the GitHub
  Pages demo runs this exact Python code with no server at all.

Each endpoint is one small function registered with ``@route``. A handler gets a
:class:`Context` (the signed-in user, the state, the request body and query) and
either returns the JSON body or raises :class:`HttpError`.
"""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime
from typing import Callable

from . import assistant, reports, rules, seed
from .permissions import ADMIN_ROLE, DEMO_ACCOUNTS, DEMO_PASSWORD, ROLES, can, permissions_of, \
    strong_password_problem
from .timeutil import DAY, iso, parse, utcnow


class HttpError(Exception):
    """An error the client should see: HTTP status + human-readable message."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------------------------- routing
Handler = Callable[..., dict]
_ROUTES: list[tuple[str, re.Pattern, Handler]] = []


def route(method: str, pattern: str):
    """Register ``fn`` for ``METHOD /api/<pattern>``. Regex groups become arguments."""
    def register(fn: Handler) -> Handler:
        _ROUTES.append((method, re.compile(f"^{pattern}$"), fn))
        return fn
    return register


class Context:
    """Everything a handler needs, plus the small helpers they share."""

    def __init__(self, state: dict, user: dict | None, query: dict, body: dict, now: datetime):
        self.state, self.user, self.query, self.body, self.now = state, user, query, body, now

    # ---- access control
    def need(self, permission: str) -> dict:
        if not self.user:
            raise HttpError(401, "Please sign in")
        if not can(self.user["role"], permission):
            raise HttpError(403, f"Your role ({self.user['role']}) cannot do this")
        return self.user

    def admin_only(self) -> dict:
        if not self.user:
            raise HttpError(401, "Please sign in")
        if self.user["role"] != ADMIN_ROLE:
            raise HttpError(403, "System Administrator only")
        return self.user

    # ---- lookups
    def aircraft(self, aircraft_id: str) -> dict:
        for ac in self.state["aircraft"]:
            if ac["aircraft_id"] == aircraft_id:
                return ac
        raise HttpError(404, f"Aircraft {aircraft_id} not found")

    def orders_of(self, aircraft_id: str) -> list[dict]:
        return [wo for wo in self.state["work_orders"] if wo["aircraft_id"] == aircraft_id]

    def work_order(self, work_order_id: str) -> dict:
        for wo in self.state["work_orders"]:
            if wo["work_order_id"] == int(work_order_id):
                return wo
        raise HttpError(404, "Work order not found")

    def account(self, username: str) -> dict:
        for u in self.state["users"]:
            if u["username"] == username:
                return u
        raise HttpError(404, f"User {username} not found")

    # ---- derived views
    def view(self, ac: dict) -> dict:
        return rules.aircraft_view(ac, self.orders_of(ac["aircraft_id"]), self.now)

    def fleet(self) -> list[dict]:
        return [self.view(ac) for ac in self.state["aircraft"]]

    def recompute(self, aircraft_id: str) -> str:
        ac = self.aircraft(aircraft_id)
        ac["ops_status"] = rules.derive_status(ac, self.orders_of(aircraft_id))
        return ac["ops_status"]

    # ---- audit log (append-only)
    def log(self, kind: str, message: str, aircraft_id: str | None = None, username: str | None = None) -> None:
        self.state["log"].append({
            "kind": kind, "message": message, "aircraft_id": aircraft_id, "created_at": iso(self.now),
            "username": username or (self.user["username"] if self.user else "system"),
        })

    def events(self, limit: int, aircraft_id: str | None = None) -> list[dict]:
        """Operational events (no security or AI entries), newest first."""
        found = [e for e in self.state["log"]
                 if not e["kind"].startswith(("SEC_", "AI_"))
                 and (aircraft_id is None or e["aircraft_id"] == aircraft_id)]
        return sorted(found, key=lambda e: e["created_at"], reverse=True)[:limit]

    def text(self, key: str, minimum: int, error: str) -> str:
        value = str(self.body.get(key) or "").strip()
        if len(value) < minimum:
            raise HttpError(400, error)
        return value


def newest_first(items: list[dict], key: str) -> list[dict]:
    return sorted(items, key=lambda x: x[key] or "", reverse=True)


# ---------------------------------------------------------------------------------- session
@route("GET", "ping")
def ping(ctx: Context) -> dict:
    """Lets the screens detect a Python server and notice changes (``rev``)."""
    return {"engine": "python", "rev": ctx.state["rev"]}


@route("POST", "login")
def login(ctx: Context) -> dict:
    name = str(ctx.body.get("username") or "").strip().lower()
    account = next((u for u in ctx.state["users"] if u["username"] == name), None)
    if not account or ctx.body.get("password") != account.get("password", DEMO_PASSWORD):
        ctx.log("SEC_LOGIN_FAILED", f"Failed sign-in for '{name}'", username=name or "?")
        raise HttpError(401, "Wrong username or password (demo password: demo)")
    if account["locked"]:
        raise HttpError(423, "Account locked after too many failed attempts — ask the administrator")
    if not account["active"]:
        raise HttpError(403, "This account is disabled")
    ctx.log("SEC_LOGIN_OK", f"{name} signed in", username=name)
    return {
        "session_token": "demo-" + name,
        "user": {"username": name, "role": account["role"]},
        "must_change_password": False,
        "two_factor_setup_required": False,
    }


@route("POST", "logout")
def logout(ctx: Context) -> dict:
    if ctx.user:
        ctx.log("SEC_LOGOUT", f"{ctx.user['username']} signed out")
    return {"message": "Signed out"}


@route("GET", "me")
def me(ctx: Context) -> dict:
    if not ctx.user:
        raise HttpError(401, "Please sign in")
    return {**ctx.user, "permissions": sorted(permissions_of(ctx.user["role"]))}


@route("POST", "account/.*")
def account_settings(ctx: Context) -> dict:
    raise HttpError(400, "Not available in the online demo")


@route("GET", "system/info")
def system_info(ctx: Context) -> dict:
    return {"lan_url": "http://skysync.local:8000"}


@route("POST", "demo/reset")
def demo_reset(ctx: Context) -> dict:
    fresh = seed.build_state(ctx.now)
    fresh["rev"] = ctx.state["rev"]
    ctx.state.clear()
    ctx.state.update(fresh)
    return {"message": "Demo data reset"}


# ---------------------------------------------------------------------------------- fleet
@route("GET", "dashboard")
def dashboard(ctx: Context) -> dict:
    ctx.need("dashboard.view")
    fleet = ctx.fleet()
    counts: dict[str, int] = {}
    for ac in fleet:
        counts[rules.status_key(ac)] = counts.get(rules.status_key(ac), 0) + 1
    average = round(sum(ac["health"]["score"] for ac in fleet) / len(fleet)) if fleet else 0
    trend = ctx.state["trend"][:-1] + [{"day": ctx.state["trend"][-1]["day"], "fleet_health": average}]
    return {"total": len(fleet), "counts": counts, "trend": trend, "aircraft": fleet,
            "events": ctx.events(12), "insight": rules.predictive_insight(fleet, ctx.now)}


@route("GET", "fleet")
def list_fleet(ctx: Context) -> dict:
    ctx.need("dashboard.view")
    return {"aircraft": ctx.fleet()}


@route("POST", "fleet")
def add_aircraft(ctx: Context) -> dict:
    ctx.need("fleet.manage")
    aircraft_id = str(ctx.body.get("aircraft_id") or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9-]{3,20}", aircraft_id):
        raise HttpError(400, "Aircraft ID: 3–20 letters, digits or dashes")
    if any(ac["aircraft_id"] == aircraft_id for ac in ctx.state["aircraft"]):
        raise HttpError(409, f"{aircraft_id} already exists")
    ctx.state["aircraft"].append({
        "aircraft_id": aircraft_id, "model": ctx.body.get("model") or seed.MODEL,
        "notes": ctx.body.get("notes") or "", "ops_status": "AVAILABLE",
        "total_flight_hours": 0.0, "hours_since_maintenance": 0.0, "last_maintenance_at": None,
        "next_due_at": iso(ctx.now + rules.INSPECTION_INTERVAL_DAYS * DAY),
    })
    ctx.log("AIRCRAFT_ADDED", f"{aircraft_id} added to the fleet", aircraft_id)
    return {"message": f"{aircraft_id} added to the fleet"}


@route("GET", "fleet/([^/]+)")
def aircraft_detail(ctx: Context, aircraft_id: str) -> dict:
    ctx.need("dashboard.view")
    ac = ctx.aircraft(aircraft_id)
    return {**ctx.view(ac), "work_orders": newest_first(ctx.orders_of(aircraft_id), "opened_at"),
            "events": ctx.events(20, aircraft_id)}


@route("GET", "components/aircraft/([^/]+)")
def components(ctx: Context, aircraft_id: str) -> dict:
    ac = ctx.aircraft(aircraft_id)
    parts = [("Engine No.1", "ENG1"), ("Engine No.2", "ENG2"), ("Main transmission", "MXMSN"),
             ("Intermediate gearbox", "IGB"), ("Tail rotor gearbox", "TGB"),
             ("Main rotor blade set", "MRB"), ("Auxiliary power unit", "APU")]
    return {"components": [{"component_name": name, "component_id": f"{ac['aircraft_id']}-{code}", "notes": ""}
                           for name, code in parts]}


# ---------------------------------------------------------------------------------- flight line
@route("POST", "fleet/([^/]+)/takeoff")
def takeoff(ctx: Context, aircraft_id: str) -> dict:
    ctx.need("flight.operate")
    ac = ctx.aircraft(aircraft_id)
    if ac["ops_status"] != "AVAILABLE":
        raise HttpError(409, f"{aircraft_id} is {ac['ops_status']} — not cleared for takeoff")
    if rules.is_overdue(ac, ctx.now):          # safety rule: overdue aircraft are grounded
        raise HttpError(409, f"{aircraft_id} is overdue for maintenance — GROUNDED")
    ac["ops_status"] = "AIRBORNE"
    ctx.state["flights"].append({"aircraft_id": aircraft_id, "takeoff_at": iso(ctx.now),
                                 "landed_at": None, "hours": None})
    ctx.log("TAKEOFF", f"{aircraft_id} – cleared for takeoff", aircraft_id)
    return {"message": f"{aircraft_id} cleared for takeoff"}


@route("POST", "fleet/([^/]+)/land")
def land(ctx: Context, aircraft_id: str) -> dict:
    ctx.need("flight.operate")
    ac = ctx.aircraft(aircraft_id)
    try:
        hours = float(ctx.body.get("flight_hours"))
    except (TypeError, ValueError):
        hours = 0.0
    if not 0 < hours <= 12:
        raise HttpError(400, "flight_hours must be between 0 and 12")
    if ac["ops_status"] != "AIRBORNE":
        raise HttpError(409, f"{aircraft_id} is not airborne")
    open_flights = [f for f in ctx.state["flights"] if f["aircraft_id"] == aircraft_id and not f["landed_at"]]
    if open_flights:
        open_flights[-1].update(landed_at=iso(ctx.now), hours=hours)
    ac["ops_status"] = "AVAILABLE"
    ac["total_flight_hours"] = round(ac["total_flight_hours"] + hours, 1)
    ac["hours_since_maintenance"] = round(ac["hours_since_maintenance"] + hours, 1)
    ctx.log("LANDED", f"{aircraft_id} – landed after {hours:.1f}h", aircraft_id)
    return {"message": f"{aircraft_id} landed — {hours:.1f}h recorded"}


@route("POST", "fleet/([^/]+)/preflight-ack")
def preflight_acknowledge(ctx: Context, aircraft_id: str) -> dict:
    ctx.need("preflight.acknowledge")
    ac = ctx.aircraft(aircraft_id)
    if ac["ops_status"] != "AVAILABLE":
        raise HttpError(409, f"{aircraft_id} is {ac['ops_status']} — not ready for flight")
    ctx.log("PREFLIGHT_ACK", f"{aircraft_id} – pre-flight review acknowledged", aircraft_id)
    return {"message": "Pre-flight review recorded"}


@route("POST", "fleet/([^/]+)/defects")
def report_defect(ctx: Context, aircraft_id: str) -> dict:
    """A pilot notices a problem → an inspection work order opens automatically."""
    ctx.need("defects.report")
    ac = ctx.aircraft(aircraft_id)
    description = ctx.text("description", 5, "describe the defect (at least 5 characters)")
    if ac["ops_status"] == "AIRBORNE":
        raise HttpError(409, "Report the defect after landing")
    _new_work_order(ctx, aircraft_id, "INSPECTION", "Pilot defect report", description, None)
    ctx.recompute(aircraft_id)
    ctx.log("DEFECT_REPORTED", f"{aircraft_id} – pilot reported: {description[:80]}", aircraft_id)
    return {"message": "Defect reported — the workshop has been notified"}


# ---------------------------------------------------------------------------------- work orders
def _new_work_order(ctx: Context, aircraft_id: str, type_: str, title: str, description: str,
                    part_name: str | None) -> dict:
    order = {
        "work_order_id": ctx.state["next_wo"], "aircraft_id": aircraft_id, "type": type_, "title": title,
        "description": description, "part_name": part_name, "status": "OPEN", "opened_at": iso(ctx.now),
        "opened_by_name": ctx.user["username"], "completed_at": None, "completed_by_name": None,
        "completion_notes": None, "signed_at": None, "signed_by_name": None, "signoff_notes": None,
    }
    ctx.state["next_wo"] += 1
    ctx.state["work_orders"].append(order)
    return order


@route("POST", "fleet/([^/]+)/work-orders")
def open_work_order(ctx: Context, aircraft_id: str) -> dict:
    ctx.need("workorders.create")
    ac = ctx.aircraft(aircraft_id)
    if ac["ops_status"] == "AIRBORNE":
        raise HttpError(409, f"{aircraft_id} is airborne — cannot open a work order")
    type_ = ctx.body.get("type")
    if type_ not in rules.TYPE_LABEL:
        raise HttpError(400, "Unknown work order type")
    title = ctx.text("title", 3, "title: give the work order a title")
    _new_work_order(ctx, aircraft_id, type_, title, str(ctx.body.get("description") or ""),
                    ctx.body.get("part_name") or None)
    ctx.recompute(aircraft_id)
    ctx.log("WO_OPENED", f"{aircraft_id} – {rules.TYPE_LABEL[type_]} ({title})", aircraft_id)
    return {"message": "Work order opened"}


@route("GET", "work-orders")
def list_work_orders(ctx: Context) -> dict:
    ctx.need("workorders.view")
    status = ctx.query.get("status")
    found = [wo for wo in ctx.state["work_orders"] if not status or wo["status"] == status]
    return {"work_orders": newest_first(found, "opened_at")}


@route("POST", r"work-orders/(\d+)/complete")
def complete_work_order(ctx: Context, work_order_id: str) -> dict:
    ctx.need("workorders.complete")
    wo = ctx.work_order(work_order_id)
    if wo["status"] != "OPEN":
        raise HttpError(409, "Only OPEN work orders can be completed")
    notes = ctx.text("notes", 3, "Describe what was done")
    wo.update(status="AWAITING_SIGNOFF", completed_by_name=ctx.user["username"],
              completed_at=iso(ctx.now), completion_notes=notes)
    ctx.recompute(wo["aircraft_id"])
    ctx.log("WO_COMPLETED", f"{wo['aircraft_id']} – work done, awaiting sign-off ({wo['title']})", wo["aircraft_id"])
    return {"message": "Submitted for sign-off"}


@route("POST", r"work-orders/(\d+)/sign-off")
def sign_off(ctx: Context, work_order_id: str) -> dict:
    """Chief engineer certifies the work — or sends it back for rework."""
    ctx.need("workorders.signoff")
    wo = ctx.work_order(work_order_id)
    aircraft_id = wo["aircraft_id"]
    if wo["status"] != "AWAITING_SIGNOFF":
        raise HttpError(409, "Work order is not awaiting sign-off")
    notes = str(ctx.body.get("notes") or "")

    if not ctx.body.get("approve"):
        wo.update(status="OPEN", completed_by_name=None, completed_at=None, signoff_notes=notes)
        ctx.recompute(aircraft_id)
        ctx.log("WO_REJECTED", f"{aircraft_id} – sign-off rejected: {notes or 'rework required'}", aircraft_id)
        return {"message": "Sent back for rework"}

    wo.update(status="CLOSED", signed_by_name=ctx.user["username"], signed_at=iso(ctx.now), signoff_notes=notes)
    if ctx.recompute(aircraft_id) == "AVAILABLE":
        # All work certified → maintenance clock restarts
        ctx.aircraft(aircraft_id).update(
            hours_since_maintenance=0.0, last_maintenance_at=iso(ctx.now),
            next_due_at=iso(ctx.now + rules.INSPECTION_INTERVAL_DAYS * DAY))
        ctx.log("AIRWORTHY", f"{aircraft_id} – certified airworthy ✔", aircraft_id)
        return {"message": f"{aircraft_id} certified airworthy"}
    ctx.log("WO_SIGNED", f"{aircraft_id} – work order signed ({wo['title']})", aircraft_id)
    return {"message": "Work order signed"}


RECORD_COLUMNS = ["opened_at", "aircraft_id", "type", "title", "part_name", "status", "opened_by_name",
                  "completed_by_name", "completion_notes", "signed_by_name", "signed_at"]


@route("GET", r"records(\.csv)?")
def records(ctx: Context, as_csv: str | None) -> dict:
    ctx.need("workorders.view")
    q = ctx.query
    search = (q.get("q") or "").lower()

    def matches(wo: dict) -> bool:
        return ((not q.get("aircraft_id") or wo["aircraft_id"] == q["aircraft_id"])
                and (not q.get("status") or wo["status"] == q["status"])
                and (not q.get("type") or wo["type"] == q["type"])
                and (not search or any(search in (wo.get(f) or "").lower()
                                       for f in ("title", "part_name", "description", "completion_notes"))))

    rows = newest_first([wo for wo in ctx.state["work_orders"] if matches(wo)], "opened_at")
    if as_csv:
        return {"__csv": reports.to_csv(rows, RECORD_COLUMNS)}
    return {"records": rows}


@route("GET", r"reports/fleet(\.csv)?")
def fleet_report(ctx: Context, as_csv: str | None) -> dict:
    ctx.need("dashboard.view")
    try:
        days = int(ctx.query.get("days") or 30)
    except ValueError:
        days = 30
    report = reports.fleet_report(ctx.state, max(1, min(days, 365)), ctx.now)
    if as_csv:
        columns = list(report["aircraft"][0]) if report["aircraft"] else []
        return {"__csv": reports.to_csv(report["aircraft"], columns)}
    return report


# ---------------------------------------------------------------------------------- AI assistant
@route("POST", "assistant/ask")
def ask(ctx: Context) -> dict:
    user = ctx.need("assistant.use")
    question = ctx.text("question", 1, "Type a question")
    result = assistant.ask(question, ctx.state, ctx.now)
    ctx.state["ai"].append({"username": user["username"], "question": question,
                            "answer": result["answer"], "created_at": iso(ctx.now)})
    ctx.log("AI_QUESTION", f"Asked: {question[:80]}")
    return result


@route("GET", "assistant/history")
def assistant_history(ctx: Context) -> dict:
    user = ctx.need("assistant.use")
    limit = int(ctx.query.get("limit") or 10)
    mine = [x for x in ctx.state["ai"] if x["username"] == user["username"]]
    return {"history": list(reversed(mine[-limit:]))}


@route("GET", "assistant/status")
def assistant_status(ctx: Context) -> dict:
    return {"documents": len(assistant.LIBRARY) + 1, "chunks": 38, "llm_model": "none online (demo answers)"}


# ---------------------------------------------------------------------------------- administrator
ACTIVITY_COLUMNS = ["created_at", "username", "kind", "aircraft_id", "message"]


@route("GET", r"admin/activity(\.csv)?")
def activity(ctx: Context, as_csv: str | None) -> dict:
    ctx.admin_only()
    q = ctx.query
    start = ctx.now - int(q.get("days") or 30) * DAY
    search = (q.get("q") or "").lower()
    in_period = [e for e in ctx.state["log"] if parse(e["created_at"]) >= start]
    matched = newest_first([
        e for e in in_period
        if (not q.get("user") or e["username"] == q["user"])
        and (not q.get("kind") or e["kind"].startswith(q["kind"]))
        and (not search or any(search in (e.get(f) or "").lower() for f in ("message", "username", "aircraft_id")))
    ], "created_at")
    if as_csv:
        return {"__csv": reports.to_csv(matched, ACTIVITY_COLUMNS)}

    def count_by(key: str) -> list[dict]:
        counts: dict[str, int] = {}
        for e in in_period:
            counts[e[key]] = counts.get(e[key], 0) + 1
        return [{key: k, "count": n} for k, n in sorted(counts.items(), key=lambda kv: -kv[1])]

    midnight = ctx.now.replace(hour=0, minute=0, second=0)
    return {
        "total_actions": len(ctx.state["log"]),
        "today": sum(1 for e in ctx.state["log"] if parse(e["created_at"]) >= midnight),
        "matched": len(matched),
        "ai_questions": len(ctx.state["ai"]) + 1,
        "by_user": count_by("username"),
        "by_kind": count_by("kind"),
        "events": matched[:200],
    }


@route("GET", "admin/overview")
def admin_overview(ctx: Context) -> dict:
    admin = ctx.admin_only()
    return {
        "online": [{"username": admin["username"], "role": admin["role"], "ip": "10.0.0.5"},
                   {"username": "tower", "role": "Tower Operator", "ip": "10.0.0.21"},
                   {"username": "engineer", "role": "Maintenance Engineer", "ip": "10.0.0.34"}],
        "require_2fa": ctx.state["require_2fa"],
        "two_factor_exempt": [name for name, _ in DEMO_ACCOUNTS],
        "roles": ROLES,
        "users": [{k: v for k, v in u.items() if k != "password"} for u in ctx.state["users"]],
        "security_log": newest_first([e for e in ctx.state["log"] if e["kind"].startswith("SEC_")], "created_at")[:30],
    }


@route("PUT", "admin/policy")
def set_policy(ctx: Context) -> dict:
    ctx.admin_only()
    ctx.state["require_2fa"] = bool(ctx.body.get("require_2fa"))
    ctx.log("SEC_POLICY", f"Mandatory 2FA {'enabled' if ctx.state['require_2fa'] else 'disabled'}")
    if ctx.state["require_2fa"]:
        return {"message": "Two-factor sign-in is now mandatory (demo accounts are exempt)"}
    return {"message": "Two-factor sign-in is optional"}


@route("POST", "admin/backup")
def backup(ctx: Context) -> dict:
    ctx.admin_only()
    ctx.log("SEC_BACKUP", "Database backup created")
    return {"message": "Backup created (demo — nothing was written)"}


@route("POST", "admin/automation/run")
def run_checks(ctx: Context) -> dict:
    ctx.admin_only()
    alerts = rules.predictive_insight(ctx.fleet(), ctx.now)["alerts"]
    ctx.log("AUTO_CHECKS", f"Automatic checks ran — {len(alerts)} alert(s)")
    return {"message": f"Checks complete — {len(alerts)} alert(s) found"}


@route("POST", "admin/users")
def create_user(ctx: Context) -> dict:
    ctx.admin_only()
    name = str(ctx.body.get("username") or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,30}", name):
        raise HttpError(400, "Username: 3–30 letters, digits, . _ -")
    if any(u["username"] == name for u in ctx.state["users"]):
        raise HttpError(409, f"{name} already exists")
    password = str(ctx.body.get("password") or "")
    problem = strong_password_problem(password)
    if problem:
        raise HttpError(400, f"Password needs {problem}")
    role = ctx.body.get("role")
    if role not in ROLES:
        raise HttpError(400, "Unknown role")
    ctx.state["users"].append({"username": name, "role": role, "active": True, "locked": False,
                               "two_factor": False, "must_change_password": False, "password": password})
    ctx.log("SEC_USER_CREATED", f"User {name} created ({role})")
    return {"message": f"{name} added — they can sign in with that password"}


@route("PUT", "admin/users/([^/]+)/status")
def set_user_status(ctx: Context, username: str) -> dict:
    ctx.admin_only()
    account = ctx.account(username)
    account["active"] = bool(ctx.body.get("active"))
    state = "enabled" if account["active"] else "disabled"
    ctx.log(f"SEC_USER_{state.upper()}", f"User {username} {state}")
    return {"message": f"{username} {state}"}


@route("POST", "admin/users/([^/]+)/unlock")
def unlock_user(ctx: Context, username: str) -> dict:
    ctx.admin_only()
    ctx.account(username)["locked"] = False
    ctx.log("SEC_USER_UNLOCKED", f"User {username} unlocked")
    return {"message": f"{username} unlocked"}


DEMO_QR = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">'
           '<rect width="200" height="200" fill="#fff"/><rect x="20" y="20" width="160" height="160" fill="none" '
           'stroke="#071226" stroke-width="6" stroke-dasharray="12 8"/><text x="100" y="96" text-anchor="middle" '
           'font-family="sans-serif" font-size="20" fill="#071226">DEMO</text><text x="100" y="122" '
           'text-anchor="middle" font-family="sans-serif" font-size="13" fill="#071226">no real QR code</text></svg>')


@route("POST", "admin/users/([^/]+)/2fa")
def enable_2fa(ctx: Context, username: str) -> dict:
    ctx.admin_only()
    ctx.account(username)["two_factor"] = True
    ctx.log("SEC_2FA_ENABLED", f"Two-factor sign-in enabled for {username}")
    return {"qr_svg": DEMO_QR, "secret": "DEMO-NOT-A-REAL-SECRET"}


@route("DELETE", "admin/users/([^/]+)/2fa")
def reset_2fa(ctx: Context, username: str) -> dict:
    ctx.admin_only()
    ctx.account(username)["two_factor"] = False
    ctx.log("SEC_2FA_RESET", f"Two-factor sign-in reset for {username}")
    return {"message": f"2FA reset for {username}"}


@route("POST", "admin/users/([^/]+)/reset-password")
def reset_password(ctx: Context, username: str) -> dict:
    ctx.admin_only()
    ctx.account(username)
    ctx.log("SEC_PASSWORD_RESET", f"Password reset for {username}")
    return {"temporary_password": "Demo-" + secrets.token_hex(3) + "!7"}


# ---------------------------------------------------------------------------------- entry points
def _user_from_token(state: dict, token: str) -> dict | None:
    if not token.startswith("demo-"):
        return None
    name = token[len("demo-"):]
    for u in state["users"]:
        if u["username"] == name and u["active"]:
            return {"username": u["username"], "role": u["role"]}
    return None


def handle(method: str, path: str, query: dict, body: dict, token: str, state: dict | None,
           now: datetime | None = None) -> tuple[int, dict, dict]:
    """
    Run one request.

    ``path`` is the part after ``/api/`` (``"fleet/SK-101/takeoff"``). Returns
    ``(status, body, state)`` — the state is returned because it may have been
    created (first visit) or replaced (demo reset).
    """
    now = now or utcnow()
    if not state or state.get("v") != seed.STATE_VERSION:
        state = seed.build_state(now)
    user = _user_from_token(state, token or "")
    ctx = Context(state, user, query or {}, body or {}, now)

    for method_, pattern, handler in _ROUTES:
        match = pattern.match(path)
        if method_ == method and match:
            if method != "GET":
                state["rev"] += 1
            try:
                return 200, handler(ctx, *match.groups()), state
            except HttpError as error:
                return error.status, {"message": error.message}, state
    return 404, {"message": f"Not available in the demo: {method} /api/{path}"}, state


def handle_json(request: str) -> str:
    """JSON in, JSON out — the bridge the browser calls through Pyodide."""
    req = json.loads(request)
    status, body, state = handle(req["method"], req["path"], req.get("query") or {}, req.get("body") or {},
                                 req.get("token") or "", req.get("state"))
    return json.dumps({"status": status, "body": body, "state": state}, ensure_ascii=False)
