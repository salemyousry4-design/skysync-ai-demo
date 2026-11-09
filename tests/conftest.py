import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skysync_demo import api, seed  # noqa: E402

NOW = datetime(2026, 11, 9, 12, 0, 0)


class Client:
    """Tiny test client: keeps the state between calls and signs in as any role."""

    def __init__(self):
        self.state = seed.build_state(NOW)
        self.now = NOW

    def call(self, method, path, body=None, user=None, **query):
        token = f"demo-{user}" if user else ""
        status, payload, self.state = api.handle(method, path, query, body or {}, token, self.state, self.now)
        return status, payload

    def aircraft(self, aircraft_id, user="commander"):
        return self.call("GET", f"fleet/{aircraft_id}", user=user)[1]


@pytest.fixture
def client():
    return Client()
