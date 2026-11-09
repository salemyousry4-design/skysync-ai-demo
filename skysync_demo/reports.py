"""
Fleet analytics.

For a period of N days, per aircraft:

* **availability** — share of the period with no open work order;
* **sorties / flight hours** — from the tower's takeoff and landing records;
* **work orders / defects** — defects are repairs and part replacements;
* **average turnaround** — hours from opening a work order to its sign-off.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

from .rules import MAINTENANCE_TYPES, aircraft_view, status_key
from .timeutil import hours_between, iso, parse


def _downtime(work_orders: list[dict], start: datetime, now: datetime) -> timedelta:
    """Total time inside [start, now] during which a work order was open."""
    total = timedelta(0)
    for wo in work_orders:
        opened = max(parse(wo["opened_at"]), start)
        closed = parse(wo["signed_at"]) if wo.get("signed_at") else now
        if closed > opened:
            total += closed - opened
    return total


def fleet_report(state: dict, days: int, now: datetime) -> dict:
    start = now - timedelta(days=days)
    period = timedelta(days=days)
    rows = []
    for ac in state["aircraft"]:
        aid = ac["aircraft_id"]
        all_orders = [wo for wo in state["work_orders"] if wo["aircraft_id"] == aid]
        orders = [wo for wo in all_orders if parse(wo["opened_at"]) >= start]
        flights = [f for f in state["flights"] if f["aircraft_id"] == aid and parse(f["takeoff_at"]) >= start]
        signed = [wo for wo in orders if wo.get("signed_at")]
        view = aircraft_view(ac, all_orders, now)
        rows.append({
            "aircraft_id": aid,
            "status": status_key(view),
            "health": view["health"]["score"],
            "availability_pct": max(0, round(100 * (1 - _downtime(all_orders, start, now) / period))),
            "sorties": len(flights),
            "flight_hours": round(sum(f["hours"] or 0 for f in flights), 1),
            "work_orders": len(orders),
            "defects": sum(1 for wo in orders if wo["type"] in MAINTENANCE_TYPES),
            "avg_turnaround_h": (round(sum(hours_between(wo["opened_at"], wo["signed_at"]) for wo in signed)
                                       / len(signed), 1) if signed else None),
        })

    def total(key: str) -> float:
        return sum(row[key] for row in rows)

    return {
        "generated_at": iso(now),
        "days": days,
        "aircraft": rows,
        "totals": {
            "availability_pct": round(total("availability_pct") / len(rows)) if rows else 0,
            "flight_hours": round(total("flight_hours"), 1),
            "sorties": int(total("sorties")),
            "work_orders": int(total("work_orders")),
            "defects": int(total("defects")),
        },
    }


def to_csv(rows: list[dict], columns: list[str]) -> str:
    """Rows → CSV text (opens directly in Excel)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({col: "" if row.get(col) is None else row.get(col) for col in columns})
    return buffer.getvalue()
