"""
Business rules — the heart of Sky Sync.

Health score (explainable, rule-based)
--------------------------------------
Every aircraft starts at 100 and loses points for concrete, human-readable
reasons. In aviation the decision has to be explainable: a commander needs to
know *why* an aircraft is at 72%, not just see the number.

==========================================  ==========================
Reason                                      Penalty
==========================================  ==========================
Hours flown since last maintenance          up to -30 (scales with use)
Repairs / part replacements, last 30 days   -5 each, up to -20
Maintenance overdue                         -10, then -2 per day, max -30
Maintenance due within 3 days               -5
Work orders not yet signed off              -8
==========================================  ==========================

Safety rules
------------
* An aircraft is **overdue** after 50 flight hours *or* 30 days since its last
  maintenance — whichever comes first. Overdue aircraft are grounded: the tower
  cannot clear them for takeoff.
* An aircraft's status is never typed in by hand. It is *derived* from its work
  orders, so the screens can never disagree with the maintenance records.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .timeutil import DAY, parse

INSPECTION_INTERVAL_HOURS = 50.0
INSPECTION_INTERVAL_DAYS = 30
MAINTENANCE_TYPES = {"REPAIR", "PART_REPLACEMENT"}

TYPE_LABEL = {
    "INSPECTION": "Inspection",
    "ROUTINE": "Routine check",
    "REPAIR": "Repair",
    "PART_REPLACEMENT": "Part replacement",
}

READY_STATUSES = ("AVAILABLE", "AIRBORNE")


def risk_level(score: float) -> str:
    """90+ → Low, 75–89 → Medium, below 75 → High."""
    if score >= 90:
        return "Low"
    if score >= 75:
        return "Medium"
    return "High"


def is_overdue(aircraft: dict, now: datetime) -> bool:
    """Overdue = 50 flight hours reached, or the next-due date has passed."""
    if (aircraft.get("hours_since_maintenance") or 0) >= INSPECTION_INTERVAL_HOURS:
        return True
    due = parse(aircraft.get("next_due_at"))
    return due is not None and due < now


def compute_health(aircraft: dict, work_orders: list[dict], now: datetime) -> dict:
    """Score 0–100, risk level and the list of reasons behind the score."""
    score = 100.0
    reasons: list[str] = []

    # 1) Flight hours since last maintenance
    hours = aircraft.get("hours_since_maintenance") or 0.0
    usage = hours / INSPECTION_INTERVAL_HOURS
    if usage > 0.2:
        penalty = min(30.0, usage * 25)
        score -= penalty
        reasons.append(f"{hours:.1f}h flown since last maintenance (-{penalty:.0f})")

    # 2) Real defects (repairs / part replacements) in the last 30 days
    since = now - timedelta(days=30)
    defects = [wo for wo in work_orders
               if wo["type"] in MAINTENANCE_TYPES and parse(wo["opened_at"]) >= since]
    if defects:
        penalty = min(20.0, len(defects) * 5)
        score -= penalty
        reasons.append(f"{len(defects)} repair/part replacement(s) in last 30 days (-{penalty:.0f})")

    # 3) Next scheduled maintenance
    due = parse(aircraft.get("next_due_at"))
    if due:
        days_left = (due - now) / DAY
        if days_left < 0:
            penalty = min(30.0, 10 + abs(days_left) * 2)
            score -= penalty
            reasons.append(f"Maintenance OVERDUE by {abs(days_left):.0f} day(s) (-{penalty:.0f})")
        elif days_left < 3:
            score -= 5
            reasons.append(f"Maintenance due in {days_left:.1f} day(s) (-5)")

    # 4) Work still open
    open_wos = [wo for wo in work_orders if wo["status"] != "CLOSED"]
    if open_wos:
        score -= 8
        reasons.append(f"{len(open_wos)} work order(s) not yet signed off (-8)")

    final = int(max(0, min(100, round(score))))
    return {"score": final, "risk": risk_level(final), "reasons": reasons}


def derive_status(aircraft: dict, work_orders: list[dict]) -> str:
    """
    The aircraft status follows from its work orders (single source of truth):

    * airborne aircraft stay AIRBORNE until the tower records the landing;
    * any OPEN repair / part replacement → UNDER_MAINTENANCE;
    * any other OPEN work order → INSPECTION;
    * work done but not yet certified → AWAITING_SIGNOFF;
    * otherwise → AVAILABLE.
    """
    if aircraft["ops_status"] == "AIRBORNE":
        return "AIRBORNE"
    active = [wo for wo in work_orders if wo["status"] == "OPEN"]
    if active:
        if any(wo["type"] in MAINTENANCE_TYPES for wo in active):
            return "UNDER_MAINTENANCE"
        return "INSPECTION"
    if any(wo["status"] == "AWAITING_SIGNOFF" for wo in work_orders):
        return "AWAITING_SIGNOFF"
    return "AVAILABLE"


def aircraft_view(aircraft: dict, work_orders: list[dict], now: datetime) -> dict:
    """The aircraft as the screens see it: stored fields + overdue + health."""
    return {
        **aircraft,
        "overdue": is_overdue(aircraft, now),
        "health": compute_health(aircraft, work_orders, now),
        "open_work_orders": sum(1 for wo in work_orders if wo["status"] != "CLOSED"),
    }


def status_key(view: dict) -> str:
    """Status used for counting: an available-but-overdue aircraft counts as GROUNDED."""
    if view["overdue"] and view["ops_status"] == "AVAILABLE":
        return "GROUNDED"
    return view["ops_status"]


def predictive_insight(fleet: list[dict], now: datetime) -> dict:
    """Summary card for the commander. ``fleet`` items are ``aircraft_view`` dicts."""
    alerts = []
    for ac in fleet:
        due = parse(ac.get("next_due_at"))
        if ac["overdue"]:
            alerts.append({"aircraft_id": ac["aircraft_id"], "level": "critical",
                           "text": f"{ac['aircraft_id']}: maintenance overdue — grounded"})
        elif ac["health"]["risk"] == "High":
            alerts.append({"aircraft_id": ac["aircraft_id"], "level": "warning",
                           "text": f"{ac['aircraft_id']}: high risk ({ac['health']['score']}%)"})
        elif due and due - now < timedelta(days=3):
            alerts.append({"aircraft_id": ac["aircraft_id"], "level": "info",
                           "text": f"{ac['aircraft_id']}: check due within 3 days"})

    week = now + timedelta(days=7)
    ready = [ac for ac in fleet
             if ac["ops_status"] in READY_STATUSES
             and not (parse(ac.get("next_due_at")) and parse(ac["next_due_at"]) < week)]
    scores = [ac["health"]["score"] for ac in fleet] or [100]
    due_dates = sorted(ac["next_due_at"] for ac in fleet if ac.get("next_due_at"))
    return {
        "ok": not alerts,
        "headline": "All Systems Normal" if not alerts else f"{len(alerts)} Alert(s) Require Attention",
        "alerts": alerts,
        "next_check": due_dates[0] if due_dates else None,
        "availability_7d": round(100 * len(ready) / len(fleet)) if fleet else 0,
        "risk_level": risk_level(sum(scores) / len(scores)),
    }
