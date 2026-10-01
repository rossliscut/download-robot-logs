"""Download an M4 log zip over HTTP. The default port is 5800."""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path

M4_PORT = 5800
M4_TYPES = (
    "system",
    "fleet",
    "rbk",
    "fleet-op",
    "scene",
    "oke",
    "falcon",
    "script",
)
JSON_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Pragma": "no-cache",
}
FILE_HEADERS = {"Accept": "*/*"}
_ISO = re.compile(
    r"(20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:\d{2})"
)


def parse_m4_types(value: str) -> list[str]:
    names = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [name for name in names if name not in M4_TYPES]
    if not names or unknown:
        allowed = ", ".join(M4_TYPES)
        raise ValueError(f"use {allowed}, got {value}")
    return names


def to_iso(value: datetime) -> str:
    """UTC ISO timestamp, matching the M4 page date picker."""
    if value.tzinfo is None:
        value = value.astimezone()
    utc = value.astimezone(timezone.utc)
    millis = utc.microsecond // 1000
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{millis:03d}Z"


def download_body(start: datetime, end: datetime, types: list[str]) -> dict[str, object]:
    return {"from": to_iso(start), "to": to_iso(end), "types": list(types)}


def files_get_path(remote: str) -> str:
    path = remote.replace("\\", "/").strip()
    if "://" in path:
        raise ValueError(f"bad file path {remote}")
    path = path.lstrip("/")
    parts = path.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"bad file path {remote}")
    return "/api/files/get/" + path


def find_clock(payload: bytes) -> datetime | None:
    """A timezone-qualified timestamp anywhere in a JSON body."""
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return _walk_clock(data)


def _walk_clock(node: object) -> datetime | None:
    if isinstance(node, str):
        match = _ISO.search(node)
        if not match:
            return None
        text, zone = match.group(1), match.group(2)
        if zone == "Z":
            zone = "+00:00"
        if "." in text:
            head, frac = text.split(".", 1)
            text = head + "." + (frac + "000000")[:6]
        return datetime.fromisoformat(text + zone)
    if isinstance(node, dict):
        for value in node.values():
            found = _walk_clock(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _walk_clock(value)
            if found is not None:
                return found
    return None


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _origin(host: str, port: int) -> str:
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{port}"


class M4Client:
    def __init__(self, host: str, port: int) -> None:
        self.origin = _origin(host, port)
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30,
    ) -> tuple[int, bytes]:
        data = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.origin + path,
            data=data,
            headers=dict(headers or {}),
            method=method,
        )
        try:
            with self.opener.open(req, timeout=timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def sign_in(self, username: str, password: str) -> None:
        _log("sign in")
        status, payload = self.request(
            "POST",
            "/api/sign-in",
            {"username": username, "password": password},
            JSON_HEADERS,
            30,
        )
        _raise_for_status(status, payload)

    def clock(self) -> datetime | None:
        for path in ("/api/base", "/api/ping"):
            status, payload = self.request("GET", path, headers=FILE_HEADERS, timeout=15)
            if status != 200:
                continue
            found = find_clock(payload)
            if found is not None:
                return found
        return None

    def request_zip(self, start: datetime, end: datetime, types: list[str]) -> str:
        status, payload = self.request(
            "POST",
            "/api/log-files/download",
            download_body(start, end, types),
            JSON_HEADERS,
            1800,
        )
        _raise_for_status(status, payload)
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("log-files/download not json") from exc
        remote = data.get("path") if isinstance(data, dict) else None
        if not isinstance(remote, str) or not remote:
            raise RuntimeError("log-files/download missing path")
        return remote

    def save_zip(self, remote: str, dest: Path) -> None:
        status, payload = self.request("GET", files_get_path(remote), headers=FILE_HEADERS, timeout=1800)
        _raise_for_status(status, payload)
        if not payload.startswith(b"PK"):
            raise RuntimeError("downloaded file is not a zip")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)


def _raise_for_status(status: int, payload: bytes) -> None:
    if 200 <= status < 300:
        return
    text = payload.decode("utf-8", errors="replace").strip()
    if status == 401:
        raise RuntimeError("401 unauthorized; pass --user and --password")
    if status == 403:
        detail = _error_detail(text)
        raise RuntimeError(f"403 forbidden{detail}")
    detail = _error_detail(text)
    raise RuntimeError(f"http {status}{detail}")


def _error_detail(text: str) -> str:
    if not text:
        return ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return " " + text[:200]
    if isinstance(data, dict):
        detail = data.get("permission") or data.get("message") or ""
        if detail:
            return " " + str(detail)
    return ""


def output_path(output: Path | None, remote: str) -> Path:
    name = remote.replace("\\", "/").rsplit("/", 1)[-1]
    if output is None:
        return Path(name)
    if output.suffix.lower() != ".zip":
        return output / name
    return output


def download_m4(
    host: str,
    port: int,
    output: Path | None,
    start: datetime | None,
    end: datetime | None,
    last: timedelta | None,
    types: list[str],
    user: str | None,
    password: str | None,
) -> Path:
    client = M4Client(host, port)
    if user is not None and password is not None:
        client.sign_in(user, password)
    if last is not None:
        now = client.clock()
        if now is None:
            _log("m4 clock not found; using this computer's clock")
            now = datetime.now().astimezone()
        else:
            _log(f"m4 time {to_iso(now)}")
        window_end = now
        window_start = now - last
    else:
        if start is None or end is None:
            raise RuntimeError("pass --last or --start and --end")
        window_start, window_end = start, end
    if to_iso(window_start) >= to_iso(window_end):
        raise RuntimeError(f"empty window {to_iso(window_start)} -> {to_iso(window_end)}")
    _log(f"window {to_iso(window_start)} -> {to_iso(window_end)}")
    remote = client.request_zip(window_start, window_end, types)
    dest = output_path(output, remote)
    _log(f"downloading {remote}")
    client.save_zip(remote, dest)
    return dest
