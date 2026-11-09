"""End-to-end tests through the API, one role at a time — like the real screens."""
import json

from skysync_demo import api


# ---------------------------------------------------------------- sign-in & permissions
def test_login_with_demo_password(client):
    status, body = client.call("POST", "login", {"username": "Tower", "password": "demo"})
    assert status == 200
    assert body["user"] == {"username": "tower", "role": "Tower Operator"}


def test_wrong_password_is_rejected_and_logged(client):
    status, _ = client.call("POST", "login", {"username": "tower", "password": "nope"})
    assert status == 401
    assert client.state["log"][-1]["kind"] == "SEC_LOGIN_FAILED"


def test_locked_and_disabled_accounts(client):
    assert client.call("POST", "login", {"username": "engineer2", "password": "demo"})[0] == 423
    assert client.call("POST", "login", {"username": "pilot2", "password": "demo"})[0] == 403


def test_requests_without_token_are_401(client):
    assert client.call("GET", "fleet")[0] == 401


def test_me_lists_permissions(client):
    _, body = client.call("GET", "me", user="tower")
    assert "flight.operate" in body["permissions"]
    assert "workorders.signoff" not in body["permissions"]


def test_pilot_cannot_clear_takeoff(client):
    status, body = client.call("POST", "fleet/SK-101/takeoff", user="pilot")
    assert status == 403 and "Pilot" in body["message"]


def test_admin_screens_are_admin_only(client):
    assert client.call("GET", "admin/overview", user="commander")[0] == 403
    assert client.call("GET", "admin/overview", user="admin")[0] == 200


# ---------------------------------------------------------------- dashboard
def test_dashboard_counts_every_aircraft(client):
    _, body = client.call("GET", "dashboard", user="commander")
    assert body["total"] == 6
    assert sum(body["counts"].values()) == 6
    assert body["counts"]["GROUNDED"] == 1          # SK-105 is overdue
    assert len(body["trend"]) == 30


def test_seed_statuses_follow_work_orders(client):
    assert client.aircraft("SK-103")["ops_status"] == "UNDER_MAINTENANCE"
    assert client.aircraft("SK-104")["ops_status"] == "AWAITING_SIGNOFF"
    assert client.aircraft("SK-102")["ops_status"] == "AIRBORNE"


# ---------------------------------------------------------------- flight line
def test_takeoff_and_landing_add_hours(client):
    before = client.aircraft("SK-101")
    assert client.call("POST", "fleet/SK-101/takeoff", user="tower")[0] == 200
    assert client.aircraft("SK-101")["ops_status"] == "AIRBORNE"
    assert client.call("POST", "fleet/SK-101/land", {"flight_hours": 1.5}, user="tower")[0] == 200
    after = client.aircraft("SK-101")
    assert after["ops_status"] == "AVAILABLE"
    assert after["hours_since_maintenance"] == round(before["hours_since_maintenance"] + 1.5, 1)


def test_overdue_aircraft_is_grounded(client):
    status, body = client.call("POST", "fleet/SK-105/takeoff", user="tower")
    assert status == 409 and "GROUNDED" in body["message"]


def test_aircraft_in_maintenance_cannot_take_off(client):
    assert client.call("POST", "fleet/SK-103/takeoff", user="tower")[0] == 409


def test_landing_hours_are_validated(client):
    assert client.call("POST", "fleet/SK-102/land", {"flight_hours": 20}, user="tower")[0] == 400
    assert client.call("POST", "fleet/SK-102/land", {"flight_hours": "abc"}, user="tower")[0] == 400


# ---------------------------------------------------------------- maintenance workflow
def test_full_maintenance_cycle(client):
    # engineer opens a repair → aircraft goes to maintenance
    status, _ = client.call("POST", "fleet/SK-106/work-orders",
                            {"type": "REPAIR", "title": "Replace landing light"}, user="engineer")
    assert status == 200
    assert client.aircraft("SK-106")["ops_status"] == "UNDER_MAINTENANCE"
    wo_id = client.state["next_wo"] - 1

    # engineer finishes → waits for the chief
    client.call("POST", f"work-orders/{wo_id}/complete", {"notes": "Light replaced, tested"}, user="engineer")
    assert client.aircraft("SK-106")["ops_status"] == "AWAITING_SIGNOFF"

    # engineer cannot certify their own work
    assert client.call("POST", f"work-orders/{wo_id}/sign-off", {"approve": True}, user="engineer")[0] == 403

    # chief certifies → available, maintenance clock restarts
    status, body = client.call("POST", f"work-orders/{wo_id}/sign-off", {"approve": True}, user="chief")
    assert status == 200 and "airworthy" in body["message"]
    after = client.aircraft("SK-106")
    assert after["ops_status"] == "AVAILABLE"
    assert after["hours_since_maintenance"] == 0


def test_rejected_work_goes_back_to_open(client):
    client.call("POST", "work-orders/107/sign-off", {"approve": False, "notes": "Torque not recorded"}, user="chief")
    order = next(w for w in client.state["work_orders"] if w["work_order_id"] == 107)
    assert order["status"] == "OPEN" and order["signoff_notes"] == "Torque not recorded"
    assert client.aircraft("SK-104")["ops_status"] == "INSPECTION"


def test_signoff_of_last_order_resets_due_date(client):
    client.call("POST", "work-orders/107/sign-off", {"approve": True}, user="chief")
    assert client.aircraft("SK-104")["next_due_at"] == "2026-12-09T12:00:00"


def test_pilot_defect_opens_inspection(client):
    status, _ = client.call("POST", "fleet/SK-101/defects", {"description": "Vibration in hover"}, user="pilot")
    assert status == 200
    assert client.aircraft("SK-101")["ops_status"] == "INSPECTION"


def test_defect_needs_a_description(client):
    assert client.call("POST", "fleet/SK-101/defects", {"description": "bad"}, user="pilot")[0] == 400


def test_cannot_open_work_order_on_airborne_aircraft(client):
    status, _ = client.call("POST", "fleet/SK-102/work-orders", {"type": "ROUTINE", "title": "Check"}, user="engineer")
    assert status == 409


# ---------------------------------------------------------------- records, reports, assistant
def test_records_filter_and_search(client):
    _, body = client.call("GET", "records", user="commander", q="fuel control")
    assert [r["aircraft_id"] for r in body["records"]] == ["SK-101"]


def test_records_csv_export(client):
    _, body = client.call("GET", "records.csv", user="commander", aircraft_id="SK-103")
    lines = body["__csv"].strip().splitlines()
    assert lines[0].startswith("opened_at,aircraft_id")
    assert len(lines) == 3          # header + 2 work orders on SK-103


def test_fleet_report_totals_match_rows(client):
    _, report = client.call("GET", "reports/fleet", user="chief", days="30")
    assert report["totals"]["sorties"] == sum(r["sorties"] for r in report["aircraft"])
    assert all(0 <= r["availability_pct"] <= 100 for r in report["aircraft"])


def test_assistant_answers_from_live_data(client):
    _, body = client.call("POST", "assistant/ask", {"question": "What is wrong with sk-103?"}, user="engineer")
    assert "SK-103 is under maintenance" in body["answer"]
    assert body["sources"][0]["title"] == "Live fleet data"


def test_assistant_cites_the_library(client):
    _, body = client.call("POST", "assistant/ask", {"question": "TGB chip light after landing"}, user="engineer")
    assert body["sources"][0]["title"] == "Drive System"


def test_assistant_refuses_to_guess(client):
    _, body = client.call("POST", "assistant/ask", {"question": "What's the weather tomorrow?"}, user="engineer")
    assert body["sources"] == [] and "will not guess" in body["answer"]


# ---------------------------------------------------------------- administration
def test_new_user_needs_a_strong_password(client):
    weak = {"username": "newpilot", "password": "short", "role": "Pilot"}
    assert client.call("POST", "admin/users", weak, user="admin")[0] == 400
    strong = {**weak, "password": "Str0ng-Passw0rd!"}
    assert client.call("POST", "admin/users", strong, user="admin")[0] == 200
    assert client.call("POST", "login", {"username": "newpilot", "password": "Str0ng-Passw0rd!"})[0] == 200


def test_password_is_never_returned(client):
    client.call("POST", "admin/users", {"username": "x-user", "password": "Str0ng-Passw0rd!", "role": "Pilot"},
                user="admin")
    _, body = client.call("GET", "admin/overview", user="admin")
    assert all("password" not in u for u in body["users"])


def test_activity_log_filters_by_kind(client):
    _, body = client.call("GET", "admin/activity", user="admin", kind="SEC_")
    assert body["events"] and all(e["kind"].startswith("SEC_") for e in body["events"])


def test_reset_restores_the_starting_fleet(client):
    client.call("POST", "fleet/SK-101/takeoff", user="tower")
    client.call("POST", "demo/reset", user="tower")
    assert client.aircraft("SK-101")["ops_status"] == "AVAILABLE"


# ---------------------------------------------------------------- browser bridge
def test_handle_json_round_trip():
    raw = api.handle_json(json.dumps({"method": "GET", "path": "fleet", "token": "demo-commander", "state": None}))
    reply = json.loads(raw)
    assert reply["status"] == 200
    assert len(reply["body"]["aircraft"]) == 6
    assert reply["state"]["v"] == 2


def test_unknown_route_is_404(client):
    assert client.call("GET", "does/not/exist", user="admin")[0] == 404
