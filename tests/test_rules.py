"""Unit tests for the business rules (health score, overdue, status)."""
from datetime import datetime, timedelta

from skysync_demo import rules
from skysync_demo.timeutil import iso

NOW = datetime(2026, 11, 9, 12, 0, 0)


def make_aircraft(hours=0.0, due_in_days=20, status="AVAILABLE"):
    return {"aircraft_id": "SK-900", "ops_status": status, "hours_since_maintenance": hours,
            "next_due_at": iso(NOW + timedelta(days=due_in_days))}


def make_order(type_="INSPECTION", status="CLOSED", days_ago=1):
    return {"type": type_, "status": status, "opened_at": iso(NOW - timedelta(days=days_ago))}


# ---------------------------------------------------------------- health score
def test_fresh_aircraft_is_100_and_low_risk():
    health = rules.compute_health(make_aircraft(), [], NOW)
    assert health == {"score": 100, "risk": "Low", "reasons": []}


def test_light_use_is_not_penalised():
    # 20% of the 50-hour interval is free
    assert rules.compute_health(make_aircraft(hours=10), [], NOW)["score"] == 100


def test_flight_hours_penalty_is_explained():
    health = rules.compute_health(make_aircraft(hours=40), [], NOW)
    assert health["score"] == 80
    assert health["reasons"] == ["40.0h flown since last maintenance (-20)"]


def test_flight_hours_penalty_is_capped_at_30():
    health = rules.compute_health(make_aircraft(hours=200), [], NOW)
    assert health["score"] == 70


def test_recent_repairs_cost_5_each_capped_at_20():
    orders = [make_order("REPAIR") for _ in range(6)]
    assert rules.compute_health(make_aircraft(), orders, NOW)["score"] == 80


def test_old_repairs_do_not_count():
    orders = [make_order("REPAIR", days_ago=45)]
    assert rules.compute_health(make_aircraft(), orders, NOW)["score"] == 100


def test_inspections_are_not_defects():
    orders = [make_order("INSPECTION")]
    assert rules.compute_health(make_aircraft(), orders, NOW)["score"] == 100


def test_overdue_penalty_grows_per_day():
    one_day = rules.compute_health(make_aircraft(due_in_days=-1), [], NOW)["score"]
    five_days = rules.compute_health(make_aircraft(due_in_days=-5), [], NOW)["score"]
    assert one_day == 88 and five_days == 80


def test_due_soon_costs_5():
    assert rules.compute_health(make_aircraft(due_in_days=2), [], NOW)["score"] == 95


def test_open_work_costs_8():
    orders = [make_order(status="OPEN")]
    assert rules.compute_health(make_aircraft(), orders, NOW)["score"] == 92


def test_score_never_negative():
    orders = [make_order("REPAIR", status="OPEN") for _ in range(10)]
    health = rules.compute_health(make_aircraft(hours=500, due_in_days=-60), orders, NOW)
    assert health["score"] >= 0
    assert health["risk"] == "High"


def test_risk_levels():
    assert [rules.risk_level(s) for s in (100, 90, 89, 75, 74)] == ["Low", "Low", "Medium", "Medium", "High"]


# ---------------------------------------------------------------- overdue
def test_overdue_by_hours():
    assert rules.is_overdue(make_aircraft(hours=50), NOW)


def test_overdue_by_date():
    assert rules.is_overdue(make_aircraft(due_in_days=-0.1), NOW)


def test_not_overdue():
    assert not rules.is_overdue(make_aircraft(hours=49.9, due_in_days=1), NOW)


# ---------------------------------------------------------------- status derivation
def test_status_available_without_work():
    assert rules.derive_status(make_aircraft(), []) == "AVAILABLE"


def test_open_repair_means_under_maintenance():
    orders = [make_order("INSPECTION", "OPEN"), make_order("REPAIR", "OPEN")]
    assert rules.derive_status(make_aircraft(), orders) == "UNDER_MAINTENANCE"


def test_open_inspection_means_inspection():
    assert rules.derive_status(make_aircraft(), [make_order("INSPECTION", "OPEN")]) == "INSPECTION"


def test_finished_work_waits_for_signoff():
    assert rules.derive_status(make_aircraft(), [make_order(status="AWAITING_SIGNOFF")]) == "AWAITING_SIGNOFF"


def test_open_work_beats_awaiting_signoff():
    orders = [make_order(status="AWAITING_SIGNOFF"), make_order("ROUTINE", "OPEN")]
    assert rules.derive_status(make_aircraft(), orders) == "INSPECTION"


def test_airborne_stays_airborne():
    orders = [make_order("REPAIR", "OPEN")]
    assert rules.derive_status(make_aircraft(status="AIRBORNE"), orders) == "AIRBORNE"


def test_overdue_available_counts_as_grounded():
    view = rules.aircraft_view(make_aircraft(hours=55), [], NOW)
    assert rules.status_key(view) == "GROUNDED"


# ---------------------------------------------------------------- predictive insight
def test_insight_all_normal():
    fleet = [rules.aircraft_view(make_aircraft(), [], NOW)]
    insight = rules.predictive_insight(fleet, NOW)
    assert insight["ok"] and insight["headline"] == "All Systems Normal"
    assert insight["availability_7d"] == 100


def test_insight_flags_overdue_first():
    fleet = [rules.aircraft_view(make_aircraft(due_in_days=-3), [], NOW)]
    insight = rules.predictive_insight(fleet, NOW)
    assert not insight["ok"]
    assert insight["alerts"][0]["level"] == "critical"
