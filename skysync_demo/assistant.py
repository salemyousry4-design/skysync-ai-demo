"""
Maintenance assistant (demo version).

The production assistant is retrieval-augmented generation running fully
offline: the question is matched against the maintenance library (hybrid
keyword + vector search), the best passages are given to a local LLM, and the
answer must cite them.

This demo keeps the same contract — *answer only from known sources, always cite
them, never guess* — with two simple sources:

1. **Live fleet data** — any question naming a tail number (``SK-103``) is answered
   from the aircraft's current status, health reasons and open work.
2. **A small library** of generic maintenance practices, matched by keywords.

If neither matches, the assistant says so instead of inventing an answer.
"""
from __future__ import annotations

import re
from datetime import datetime

from .rules import aircraft_view

LIBRARY = [
    {
        "keys": ["chip", "tgb", "gearbox"],
        "title": "Drive System", "section": "Chip detector indications",
        "text": "A chip indication means metal particles were collected by the magnetic detector.",
        "answer": (
            "1. Treat a chip light as a real indication until proven otherwise [1].\n"
            "2. After shutdown, remove and inspect the chip detector: fine fuzz is usually normal wear, "
            "flakes or chunks are not [1].\n"
            "3. Take an oil sample and check the oil level and filter bypass indicator [2].\n"
            "4. If particles exceed limits, open a REPAIR work order and do not release the aircraft "
            "until the chief engineer signs it off.\n\n"
            "Always follow the approved technical manual for the exact limits."
        ),
    },
    {
        "keys": ["bounce", "vibration", "track", "blade", "rotor"],
        "title": "Rotor System", "section": "Vibration & tracking",
        "text": "Vertical bounce after blade work is most often a track or balance issue.",
        "answer": (
            "Vertical bounce after a blade change is usually track and balance [1]:\n"
            "1. Run a track & balance check with the vibration analysis kit.\n"
            "2. Adjust pitch links / trim tabs as the analysis recommends [1].\n"
            "3. Re-fly and confirm the readings are within limits before sign-off [2]."
        ),
    },
    {
        "keys": ["hydraulic", "leak", "fitting", "seep"],
        "title": "Hydraulic System", "section": "Leak classification",
        "text": "Leaks are classified by drops per minute: seep, weep, leak, running leak.",
        "answer": (
            "Classify the leak first [1]: count drops per minute after wiping the area clean.\n"
            "• Seep / weep: monitor and record.\n"
            "• Leak / running leak: open a REPAIR work order before the next flight [2].\n"
            "Check torque on the fitting and the condition of the seal; never over-torque to stop a leak."
        ),
    },
    {
        "keys": ["fuel", "fcu", "engine", "start"],
        "title": "Powerplant", "section": "Fuel system troubleshooting",
        "text": "Start problems are traced in order: power, fuel, ignition.",
        "answer": (
            "Trace engine start problems in order: electrical power → fuel supply → ignition [1].\n"
            "Check fuel filters and the fuel control unit indications, then compare with the "
            "troubleshooting table [2]. Record every finding in the work order."
        ),
    },
]

GENERAL_PRACTICES = {
    "title": "General Maintenance Practices", "section": "Inspection & sign-off",
    "text": "Every repair is certified by the chief engineer.",
}

MODE = "Demo — library answers (the real system runs a local LLM + RAG, fully offline)"
TAIL_NUMBER = re.compile(r"\b[A-Z]{2}-\d{3}\b")


def _pretty(status: str) -> str:
    return status.replace("_", " ").lower()


def answer_about_aircraft(aircraft: dict, work_orders: list[dict], now: datetime) -> str:
    view = aircraft_view(aircraft, work_orders, now)
    open_work = [wo for wo in work_orders if wo["status"] != "CLOSED"]
    lines = [
        f"{view['aircraft_id']} is {_pretty(view['ops_status'])}"
        f"{' and OVERDUE (grounded)' if view['overdue'] else ''}. "
        f"Health {view['health']['score']}% (risk {view['health']['risk']})."
    ]
    if view["health"]["reasons"]:
        lines.append("Why: " + "; ".join(view["health"]["reasons"]) + ".")
    if open_work:
        lines.append("Open work: " + ", ".join(f"{wo['title']} ({_pretty(wo['status'])})" for wo in open_work) + ".")
    else:
        lines.append("No open work orders.")
    lines.append("[live fleet data]")
    return "\n".join(lines)


def ask(question: str, state: dict, now: datetime) -> dict:
    """Answer a question. Returns ``{answer, sources, mode}`` like the production API."""
    match = TAIL_NUMBER.search(question.upper())
    if match:
        aircraft = next((a for a in state["aircraft"] if a["aircraft_id"] == match.group()), None)
        if aircraft:
            orders = [wo for wo in state["work_orders"] if wo["aircraft_id"] == aircraft["aircraft_id"]]
            return {
                "answer": answer_about_aircraft(aircraft, orders, now),
                "sources": [{"n": 1, "title": "Live fleet data", "section": aircraft["aircraft_id"],
                             "text": "Current status from the database"}],
                "mode": MODE,
            }

    text = question.lower()
    for doc in LIBRARY:
        if any(key in text for key in doc["keys"]):
            return {
                "answer": doc["answer"],
                "sources": [
                    {"n": 1, "title": doc["title"], "section": doc["section"], "text": doc["text"]},
                    {"n": 2, **GENERAL_PRACTICES},
                ],
                "mode": MODE,
            }

    return {
        "answer": ("I could not find this in the maintenance library, so I will not guess.\n"
                   "Try asking about a chip light, rotor vibration, a hydraulic leak, an engine start "
                   "problem — or an aircraft like SK-103."),
        "sources": [],
        "mode": MODE,
    }
