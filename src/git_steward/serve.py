from __future__ import annotations

import json
import socket
import threading
from contextlib import closing
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from .config import Config
from .dashboard import render_dashboard
from .git_status import scan_all
from .history import record_run
from .state import read_latest, write_latest

PORT_RANGES: list[tuple[str, int]] = [
    ("Vite", 5173),
    ("Next.js", 3000),
    ("Astro", 4321),
    ("SvelteKit", 5173),
    ("Remix", 3000),
    ("Nuxt", 3000),
    ("Django", 8000),
    ("Rails", 3000),
    ("Flask", 5000),
    ("FastAPI", 8000),
    ("Express", 3000),
    ("CRA", 3000),
    ("VitePress", 4173),
    ("Storybook", 6006),
    ("Tauri", 1420),
    ("Jekyll", 4000),
    ("Hugo", 1313),
    ("Eleventy", 8080),
    ("Webpack dev", 8080),
    ("Live Server", 5500),
    ("Livereload", 35729),
]


def _port_in_use(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _deduped_ports() -> list[tuple[str, int]]:
    seen: set[int] = set()
    result: list[tuple[str, int]] = []
    for name, port in PORT_RANGES:
        if port not in seen:
            seen.add(port)
            result.append((name, port))
    return result


def detect_dev_servers() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for name, port in _deduped_ports():
        if _port_in_use(port):
            found.append({"name": name, "port": port, "url": f"http://localhost:{port}"})
    return found


class _Handler(BaseHTTPRequestHandler):
    server_instance: ServeServer

    def _send_json(self, status: int, data: object) -> None:
        payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload.encode())

    def _send_html(self, status: int, html: str) -> None:
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        sv = self.server_instance
        if self.path == "/api/latest.json":
            try:
                data = read_latest(sv.config)
            except FileNotFoundError:
                self._send_json(503, {"error": "no scan data yet"})
                return
            self._send_json(200, data)
        elif self.path == "/api/ports":
            ports = detect_dev_servers()
            self._send_json(200, {"ports": ports, "count": len(ports)})
        elif self.path == "/api/scan":
            try:
                summary, statuses = scan_all(sv.config, fetch=False)
                record_run(sv.config, summary, statuses)
                write_latest(sv.config, summary)
                render_dashboard(sv.config, summary)
                sv._latest = summary
                self._send_json(200, {"status": "ok", "finished_at": summary.get("finished_at")})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
        elif self.path in ("/", "/dashboard"):
            try:
                summary = read_latest(sv.config)
            except FileNotFoundError:
                summary = sv._latest or {}
            from .dashboard import render_html

            self._send_html(200, render_html(summary, sv.config.refresh_seconds))
        elif self.path == "/api":
            eps = ["/", "/dashboard", "/api", "/api/latest.json", "/api/ports", "/api/scan"]
            self._send_json(200, {"endpoints": eps})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


class ServeServer:
    def __init__(self, config: Config, port: int = 8199) -> None:
        self.config = config
        self.port = port
        self._latest: dict[str, object] = {}
        self._stop_event = threading.Event()

    def _rescan_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                summary, statuses = scan_all(self.config, fetch=False)
                record_run(self.config, summary, statuses)
                write_latest(self.config, summary)
                render_dashboard(self.config, summary)
                self._latest = summary
            except Exception:
                pass
            self._stop_event.wait(self.config.refresh_seconds)

    def serve_forever(self) -> None:
        _Handler.server_instance = self
        server = HTTPServer(("127.0.0.1", self.port), _Handler)
        print(f"Serving dashboard at http://127.0.0.1:{self.port}/")
        print(f"API at http://127.0.0.1:{self.port}/api")
        print("Press Ctrl+C to stop.")

        rescan = threading.Thread(target=self._rescan_loop, daemon=True)
        rescan.start()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down…")
            self._stop_event.set()
            server.shutdown()
