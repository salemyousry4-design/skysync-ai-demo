"""
The fictional starting fleet.

Six aircraft (tail numbers ``SK-101`` … ``SK-106`` are made up), chosen so every
part of the system has something to show on first load:

========  ===========================================================
SK-101    available, healthy, recent fuel control unit replacement
SK-102    airborne right now
SK-103    under maintenance — tail rotor gearbox chip light
SK-104    inspection done, waiting for the chief engineer's sign-off
SK-105    overdue for maintenance → grounded
SK-106    freshly inspected, 100% health
========  ===========================================================

The data is generated relative to "now" with a fixed random seed, so the demo
always looks current but is reproducible in tests.
"""
from __future__ import annotations

import math
import random
from datetime import datetime

from .permissions import DEMO_ACCOUNTS
from .rules import derive_status
from .timeutil import DAY, HOUR, MINUTE, iso, parse

STATE_VERSION = 2
MODEL = "AH-64D"


def _aircraft(aircraft_id: str, now: datetime, *, hours_total: float, hours_since: float,
              maintained_days_ago: float, due_in_days: float, status: str = "AVAILABLE") -> dict:
    return {
        "aircraft_id": aircraft_id, "model": MODEL, "notes": "", "ops_status": status,
        "total_flight_hours": hours_total, "hours_since_maintenance": hours_since,
        "last_maintenance_at": iso(now - maintained_days_ago * DAY),
        "next_due_at": iso(now + due_in_days * DAY),
    }


def _work_order(wo_id: int, aircraft_id: str, type_: str, title: str, **fields) -> dict:
    order = {
        "work_order_id": wo_id, "aircraft_id": aircraft_id, "type": type_, "title": title,
        "description": "", "part_name": None, "status": "CLOSED", "opened_at": None,
        "opened_by_name": "engineer", "completed_at": None, "completed_by_name": None,
        "completion_notes": None, "signed_at": None, "signed_by_name": None, "signoff_notes": None,
    }
    order.update(fields)
    return order


def _closed(wo_id: int, aircraft_id: str, type_: str, title: str, days_ago: float, notes: str,
            now: datetime, part: str | None = None) -> dict:
    opened = now - days_ago * DAY
    return _work_order(
        wo_id, aircraft_id, type_, title, part_name=part, opened_at=iso(opened),
        completed_at=iso(opened + 20 * HOUR), completed_by_name="engineer", completion_notes=notes,
        signed_at=iso(opened + 26 * HOUR), signed_by_name="chief",
    )


def build_state(now: datetime) -> dict:
    """A fresh demo state: fleet, work orders, flights, activity log, users."""
    rnd = random.Random(7)

    aircraft = [
        _aircraft("SK-101", now, hours_total=1243.5, hours_since=12.4, maintained_days_ago=9, due_in_days=21),
        _aircraft("SK-102", now, hours_total=987.2, hours_since=31.0, maintained_days_ago=18, due_in_days=12,
                  status="AIRBORNE"),
        _aircraft("SK-103", now, hours_total=1508.9, hours_since=44.2, maintained_days_ago=26, due_in_days=4),
        _aircraft("SK-104", now, hours_total=765.0, hours_since=47.1, maintained_days_ago=29, due_in_days=1),
        _aircraft("SK-105", now, hours_total=1120.3, hours_since=51.6, maintained_days_ago=32, due_in_days=-2),
        _aircraft("SK-106", now, hours_total=402.7, hours_since=3.5, maintained_days_ago=2, due_in_days=28),
    ]

    work_orders = [
        _closed(101, "SK-104", "ROUTINE", "Main rotor blade tracking", 40, "Tracking within limits.", now),
        _closed(102, "SK-105", "INSPECTION", "30-day calendar inspection", 33, "Inspection complete, no findings.", now),
        _closed(103, "SK-103", "REPAIR", "Hydraulic fitting leak — utility system", 22,
                "Fitting re-torqued, leak check passed.", now),
        _closed(104, "SK-102", "ROUTINE", "Post-flight check", 19, "Completed, no defects.", now),
        _closed(105, "SK-101", "PART_REPLACEMENT", "Fuel control unit replacement", 10,
                "Unit replaced, engine ground run OK.", now, part="Fuel Control Unit"),
        _closed(106, "SK-106", "INSPECTION", "50-hour phased inspection", 3, "All items inspected, no findings.", now),
        _work_order(107, "SK-104", "INSPECTION", "50-hour phased inspection", status="AWAITING_SIGNOFF",
                    opened_at=iso(now - 30 * HOUR), completed_at=iso(now - 3 * HOUR), completed_by_name="engineer",
                    completion_notes="Phase inspection complete. Minor chafing on a cable clamp corrected."),
        _work_order(108, "SK-103", "REPAIR", "Tail rotor gearbox chip light", status="OPEN",
                    part_name="TGB chip detector", opened_at=iso(now - 6 * HOUR),
                    description="Chip light illuminated after landing. Inspect detector and gearbox oil."),
    ]

    # ~90 days of flying history (sorties of 1–3 hours)
    flights = []
    for ac in aircraft:
        for days_ago in range(89, 0, -1):
            if rnd.random() < 0.33:
                takeoff = now - days_ago * DAY + (8 + rnd.randrange(6)) * HOUR
                hours = round(1 + rnd.random() * 2, 1)
                flights.append({"aircraft_id": ac["aircraft_id"], "takeoff_at": iso(takeoff),
                                "landed_at": iso(takeoff + hours * HOUR), "hours": hours})
    flights.append({"aircraft_id": "SK-102", "takeoff_at": iso(now - 50 * MINUTE), "landed_at": None, "hours": None})

    log = []

    def event(minutes_ago: float, kind: str, message: str, username: str, aircraft_id: str | None = None):
        log.append({"kind": kind, "message": message, "username": username, "aircraft_id": aircraft_id,
                    "created_at": iso(now - minutes_ago * MINUTE)})

    for f in flights:
        if f["landed_at"] and parse(f["takeoff_at"]) > now - 3 * DAY:
            log.append({"kind": "TAKEOFF", "message": f"{f['aircraft_id']} – cleared for takeoff", "username": "tower",
                        "aircraft_id": f["aircraft_id"], "created_at": f["takeoff_at"]})
            log.append({"kind": "LANDED", "message": f"{f['aircraft_id']} – landed after {f['hours']:.1f}h",
                        "username": "tower", "aircraft_id": f["aircraft_id"], "created_at": f["landed_at"]})
    event(2 * 1440 + 200, "AIRWORTHY", "SK-106 – certified airworthy ✔", "chief", "SK-106")
    event(1800, "WO_OPENED", "SK-104 – Inspection (50-hour phased inspection)", "engineer", "SK-104")
    event(400, "SEC_LOGIN_FAILED", "Failed sign-in for 'enginer' (unknown user)", "enginer")
    event(362, "DEFECT_REPORTED", "SK-103 – pilot reported: chip light after landing", "pilot", "SK-103")
    event(360, "WO_OPENED", "SK-103 – Repair (Tail rotor gearbox chip light)", "engineer", "SK-103")
    event(240, "AI_QUESTION", "Asked: TGB chip light after landing — what do I do?", "engineer")
    event(180, "WO_COMPLETED", "SK-104 – work done, awaiting sign-off (50-hour phased inspection)", "engineer", "SK-104")
    event(95, "PREFLIGHT_ACK", "SK-101 – pre-flight review acknowledged", "pilot", "SK-101")
    event(52, "SEC_LOGIN_OK", "tower signed in", "tower")
    event(50, "TAKEOFF", "SK-102 – cleared for takeoff", "tower", "SK-102")

    # 30-day fleet health history for the trend chart
    trend = []
    for days_ago in range(29, -1, -1):
        day = (now - days_ago * DAY).replace(hour=0, minute=0, second=0)
        value = 84 + 5 * math.sin(days_ago / 4) + (rnd.random() - 0.5) * 4
        trend.append({"day": iso(day), "fleet_health": round(value)})

    users = [{"username": name, "role": role, "active": True, "locked": False,
              "two_factor": name == "admin", "must_change_password": False}
             for name, role in DEMO_ACCOUNTS]
    users.append({"username": "engineer2", "role": "Maintenance Engineer", "active": True, "locked": True,
                  "two_factor": False, "must_change_password": False})
    users.append({"username": "pilot2", "role": "Pilot", "active": False, "locked": False,
                  "two_factor": False, "must_change_password": False})

    for ac in aircraft:
        ac["ops_status"] = derive_status(ac, [wo for wo in work_orders if wo["aircraft_id"] == ac["aircraft_id"]])

    return {
        "v": STATE_VERSION, "rev": 0, "aircraft": aircraft, "work_orders": work_orders, "flights": flights,
        "log": log, "trend": trend, "users": users, "ai": [], "require_2fa": False, "next_wo": 109,
    }
