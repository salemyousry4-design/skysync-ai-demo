"""
Sky Sync AI — demo engine.

The same business rules as the production Sky Sync server, written as a small,
dependency-free Python package so the demo can run anywhere:

* in the browser (GitHub Pages) through Pyodide — see ``demo.js``;
* locally over HTTP with ``python server.py``;
* under pytest — see ``tests/``.

Modules
-------
timeutil     time helpers (naive-UTC ISO strings, the format the screens use)
rules        health score, overdue rule, status derivation, predictive insight
permissions  roles, permissions and the demo accounts
seed         the fictional starting fleet
assistant    the maintenance assistant (canned library answers in the demo)
reports      fleet analytics and CSV export
api          the /api/... endpoints, one function per route
"""

__version__ = "1.0.0"
