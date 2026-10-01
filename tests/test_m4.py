import json
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from download_robot_logs.cli import main
from download_robot_logs.m4 import (
    M4_PORT,
    M4_TYPES,
    download_body,
    download_m4,
    files_get_path,
    find_clock,
    parse_m4_types,
    to_iso,
)


class M4LayoutTest(unittest.TestCase):
    def test_iso_and_download_body(self) -> None:
        start = datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 1, 19, 0, tzinfo=timezone.utc)
        self.assertEqual(to_iso(end), "2026-10-01T19:00:00.000Z")
        body = download_body(start, end, list(M4_TYPES))
        self.assertEqual(body["from"], "2026-10-01T18:00:00.000Z")
        self.assertEqual(body["to"], "2026-10-01T19:00:00.000Z")
        self.assertEqual(body["types"], list(M4_TYPES))

    def test_file_path_and_types(self) -> None:
        self.assertEqual(
            files_get_path("tmp/m4-logs-2026100115-2026100115.zip"),
            "/api/files/get/tmp/m4-logs-2026100115-2026100115.zip",
        )
        self.assertEqual(
            files_get_path("/tmp/m4-logs-2026100115-2026100115.zip"),
            "/api/files/get/tmp/m4-logs-2026100115-2026100115.zip",
        )
        with self.assertRaises(ValueError):
            files_get_path("../etc/passwd")
        self.assertEqual(parse_m4_types("system, fleet"), ["system", "fleet"])
        with self.assertRaises(ValueError):
            parse_m4_types("system,nope")

    def test_clock_needs_a_zone(self) -> None:
        self.assertEqual(
            find_clock(b'{"now":"2026-10-01T19:00:00.000Z"}'),
            datetime(2026, 10, 1, 19, 0, tzinfo=timezone.utc),
        )
        self.assertIsNone(find_clock(b'{"serviceVersionName":"trick-m4-0928-1536"}'))
        self.assertIsNone(find_clock(b'{"username":"Ross"}'))

    def test_cli_rejects_mixed_flags(self) -> None:
        self.assertEqual(main(["--host", "127.0.0.1", "--m4", "--rds", "--last", "10m"]), 2)
        self.assertEqual(main(["--host", "127.0.0.1", "--m4"]), 2)
        self.assertEqual(main(["--host", "127.0.0.1", "--m4", "--last", "10m", "--user", "a"]), 2)
        self.assertEqual(main(["--host", "127.0.0.1", "--last", "10m", "--types", "system"]), 2)

    def test_cli_defaults_m4_port(self) -> None:
        with patch("download_robot_logs.cli.download_m4", return_value=Path("a.zip")) as call:
            code = main(["--host", "10.0.0.8", "--m4", "--last", "10m"])
        self.assertEqual(code, 0)
        self.assertEqual(call.call_args.args[1], M4_PORT)
        with patch("download_robot_logs.cli.download_m4", return_value=Path("a.zip")) as call:
            main(["--host", "10.0.0.8", "--m4", "--port", "5801", "--last", "10m"])
        self.assertEqual(call.call_args.args[1], 5801)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _read(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length)

    def _record(self, body: bytes) -> None:
        self.server.seen.append((self.command, self.path, dict(self.headers), body))  # type: ignore[attr-defined]

    def do_POST(self) -> None:  # noqa: N802
        body = self._read()
        self._record(body)
        if self.path == "/api/sign-in":
            self.send_response(200)
            self.send_header("Set-Cookie", "sid=abc; HttpOnly; Path=/")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")
            return
        if self.path == "/api/log-files/download":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"path":"tmp/m4-logs-test.zip"}')
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._record(b"")
        if self.path == "/api/base":
            payload = b'{"serviceVersionName":"trick-m4"}'
        elif self.path == "/api/ping":
            payload = b'{"now":"2026-10-01T19:00:00.000Z"}'
        elif self.path == "/api/files/get/tmp/m4-logs-test.zip":
            payload = b"PK\x03\x04zip"
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class M4DownloadTest(unittest.TestCase):
    def test_sign_in_cookie_and_window(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.seen = []  # type: ignore[attr-defined]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            dest = download_m4(
                host,
                port,
                Path(self.id().replace(".", "_")),
                None,
                None,
                timedelta(hours=1),
                ["system", "fleet"],
                "Ross",
                "secret",
            )
            self.assertEqual(dest.name, "m4-logs-test.zip")
            self.assertEqual(dest.read_bytes(), b"PK\x03\x04zip")
        finally:
            server.shutdown()
            server.server_close()
            dest = Path(self.id().replace(".", "_")) / "m4-logs-test.zip"
            if dest.exists():
                dest.unlink()
            if dest.parent.exists():
                dest.parent.rmdir()
        seen = server.seen  # type: ignore[attr-defined]
        sign_in = seen[0]
        self.assertEqual(sign_in[0:2], ("POST", "/api/sign-in"))
        self.assertEqual(json.loads(sign_in[3]), {"username": "Ross", "password": "secret"})
        self.assertEqual(sign_in[2]["Pragma"], "no-cache")
        download = next(item for item in seen if item[1] == "/api/log-files/download")
        self.assertIn("sid=abc", download[2]["Cookie"])
        self.assertEqual(download[2]["Content-Type"], "application/json")
        self.assertEqual(download[2]["Accept"], "application/json, text/plain, */*")
        body = json.loads(download[3])
        self.assertEqual(body["from"], "2026-10-01T18:00:00.000Z")
        self.assertEqual(body["to"], "2026-10-01T19:00:00.000Z")
        self.assertEqual(body["types"], ["system", "fleet"])
        fetched = next(item for item in seen if item[1] == "/api/files/get/tmp/m4-logs-test.zip")
        self.assertEqual(fetched[0], "GET")
        self.assertEqual(fetched[2]["Accept"], "*/*")
        self.assertNotIn("Content-Type", fetched[2])
        self.assertIn("sid=abc", fetched[2]["Cookie"])


if __name__ == "__main__":
    unittest.main()
