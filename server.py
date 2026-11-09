"""
Run the Sky Sync demo locally — standard library only, nothing to install.

    python server.py            # http://localhost:8000
    python server.py --port 9000

Serves the screens and answers ``/api/...`` with the Python engine in
``skysync_demo``. Unlike the GitHub Pages version (where each browser keeps its
own data), here every browser and device on your network shares one fleet:
open the Tower on a phone and the Commander on a laptop and watch them sync.
"""
from __future__ import annotations

import argparse
import json
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from skysync_demo import api

ROOT = Path(__file__).resolve().parent
_state: dict | None = None
_lock = threading.Lock()


class DemoHandler(SimpleHTTPRequestHandler):
    """Static files from the project folder + the JSON API under /api/."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    # ---- HTTP verbs
    def do_GET(self):
        if self.path.startswith("/api/"):
            self._api("GET")
        else:
            super().do_GET()

    def do_POST(self):
        self._api("POST")

    def do_PUT(self):
        self._api("PUT")

    def do_DELETE(self):
        self._api("DELETE")

    # ---- API
    def _api(self, method: str) -> None:
        global _state
        url = urlsplit(self.path)
        if not url.path.startswith("/api/"):
            return self._send(HTTPStatus.NOT_FOUND, {"message": "Not found"})
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        except json.JSONDecodeError:
            return self._send(HTTPStatus.BAD_REQUEST, {"message": "Body must be JSON"})
        token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()

        with _lock:                                   # one request at a time changes the fleet
            status, payload, _state = api.handle(method, url.path[len("/api/"):], dict(parse_qsl(url.query)),
                                                 body if isinstance(body, dict) else {}, token, _state)
        self._send(status, payload)

    def _send(self, status: int, payload: dict) -> None:
        if "__csv" in payload:
            data, content_type = payload["__csv"].encode("utf-8-sig"), "text/csv; charset=utf-8"
        else:
            data, content_type = json.dumps(payload, ensure_ascii=False).encode(), "application/json"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):            # quieter console: only API calls
        if "/api/" in (args[0] if args else "") and "/api/ping" not in args[0]:
            super().log_message(fmt, *args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sky Sync AI demo server")
    parser.add_argument("--host", default="0.0.0.0", help="0.0.0.0 = reachable from phones on the same Wi-Fi")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"Sky Sync demo running at http://localhost:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
