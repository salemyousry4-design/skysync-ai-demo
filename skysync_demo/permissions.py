"""
Roles and permissions (role-based access control).

Each screen asks ``/api/me`` for the signed-in user's permissions and disables the
buttons that role cannot use. The API checks the same permissions again on every
request — the screen is a convenience, the server is the guard.
"""
from __future__ import annotations

ROLES = [
    "System Administrator",
    "Commander",
    "Tower Operator",
    "Chief Engineer",
    "Maintenance Manager",
    "Maintenance Engineer",
    "Pilot",
]

ADMIN_ROLE = "System Administrator"

# Everyone who can sign in may see the fleet and ask the assistant.
_BASE = {"dashboard.view", "workorders.view", "assistant.use"}

PERMISSIONS: dict[str, set[str]] = {
    "System Administrator": _BASE | {
        "workorders.create", "workorders.complete", "workorders.signoff", "flight.operate",
        "defects.report", "preflight.acknowledge", "fleet.manage", "reports.view",
    },
    "Commander": _BASE | {"reports.view"},
    "Tower Operator": {"dashboard.view", "workorders.view", "flight.operate"},
    "Chief Engineer": _BASE | {
        "workorders.create", "workorders.complete", "workorders.signoff", "fleet.manage", "reports.view",
    },
    "Maintenance Manager": _BASE | {"workorders.create", "workorders.complete", "reports.view"},
    "Maintenance Engineer": _BASE | {"workorders.create", "workorders.complete"},
    "Pilot": _BASE | {"defects.report", "preflight.acknowledge"},
}

# (username, role) — every demo account signs in with the password "demo".
DEMO_ACCOUNTS = [
    ("commander", "Commander"),
    ("tower", "Tower Operator"),
    ("engineer", "Maintenance Engineer"),
    ("chief", "Chief Engineer"),
    ("pilot", "Pilot"),
    ("admin", "System Administrator"),
]
DEMO_PASSWORD = "demo"


def permissions_of(role: str) -> set[str]:
    return set(PERMISSIONS.get(role, set()))


def can(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())


def strong_password_problem(password: str) -> str | None:
    """Return why a password is too weak, or ``None`` if it is acceptable."""
    if len(password) < 12:
        return "at least 12 characters"
    if not any(c.islower() for c in password) or not any(c.isupper() for c in password):
        return "upper- and lowercase letters"
    if not any(c.isdigit() for c in password):
        return "at least one digit"
    if all(c.isalnum() for c in password):
        return "at least one symbol"
    return None
