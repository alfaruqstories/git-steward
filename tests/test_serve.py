import json
import socket
import threading
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import urlopen

from git_steward.config import Config, Root
from git_steward.serve import ServeServer, _port_in_use, detect_dev_servers


def _unused_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _mini_config(tmp: Path) -> Config:
    return Config(
        path=tmp / "config.toml",
        roots=[Root(tmp)],
        state_dir=tmp,
        redact_paths=False,
    )


class ServeTests(unittest.TestCase):
    def test_port_in_use_on_known_closed_port(self):
        self.assertFalse(_port_in_use(19999))

    def test_port_in_use_on_known_open_port(self):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            s.listen()
            self.assertTrue(_port_in_use(port))

    def test_detect_dev_servers_returns_empty_when_none_running(self):
        found = detect_dev_servers()
        self.assertIsInstance(found, list)

    def test_serve_returns_json_for_api_root(self):
        with TemporaryDirectory() as tmp:
            config = _mini_config(Path(tmp))
            port = _unused_port()
            server = ServeServer(config, port=port, refresh_seconds=0)

            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()

            import time

            time.sleep(0.1)

            resp = urlopen(f"http://127.0.0.1:{port}/api")
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers["Content-Type"], "application/json")
            data = json.loads(resp.read())
            self.assertIn("endpoints", data)

    def test_serve_returns_404_for_unknown_path(self):
        with TemporaryDirectory() as tmp:
            config = _mini_config(Path(tmp))
            port = _unused_port()
            server = ServeServer(config, port=port, refresh_seconds=0)

            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()

            import time

            time.sleep(0.1)

            with self.assertRaises(HTTPError) as ctx:
                urlopen(f"http://127.0.0.1:{port}/api/nonexistent")
            self.assertEqual(ctx.exception.code, 404)

    def test_serve_dashboard_returns_html_when_no_data(self):
        with TemporaryDirectory() as tmp:
            config = _mini_config(Path(tmp))
            port = _unused_port()
            server = ServeServer(config, port=port, refresh_seconds=0)

            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()

            import time

            time.sleep(0.1)

            resp = urlopen(f"http://127.0.0.1:{port}/")
            self.assertEqual(resp.status, 200)
            content = resp.read().decode()
            self.assertIn("Git Steward", content)
            self.assertIn("text/html", resp.headers["Content-Type"])

    def test_serve_ports_endpoint_returns_json(self):
        with TemporaryDirectory() as tmp:
            config = _mini_config(Path(tmp))
            port = _unused_port()
            server = ServeServer(config, port=port, refresh_seconds=0)

            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()

            import time

            time.sleep(0.1)

            resp = urlopen(f"http://127.0.0.1:{port}/api/ports")
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read())
            self.assertIn("ports", data)
            self.assertIn("count", data)

    def test_serve_scan_endpoint_triggers_scan(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "a-repo").mkdir()
            config = Config(
                path=tmp / "config.toml",
                roots=[Root(tmp)],
                state_dir=tmp,
                redact_paths=False,
                repos=[tmp / "a-repo"],
            )
            port = _unused_port()
            server = ServeServer(config, port=port, refresh_seconds=0)

            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()

            import time

            time.sleep(0.1)

            resp = urlopen(f"http://127.0.0.1:{port}/api/scan")
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read())
            self.assertEqual(data["status"], "ok")

    def test_latest_json_endpoint_fails_gracefully_when_no_data(self):
        with TemporaryDirectory() as tmp:
            config = _mini_config(Path(tmp))
            port = _unused_port()
            server = ServeServer(config, port=port, refresh_seconds=0)

            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()

            import time

            time.sleep(0.1)

            with self.assertRaises(HTTPError) as ctx:
                urlopen(f"http://127.0.0.1:{port}/api/latest.json")
            self.assertEqual(ctx.exception.code, 503)


if __name__ == "__main__":
    unittest.main()
