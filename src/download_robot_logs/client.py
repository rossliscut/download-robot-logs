"""Robod TCP framing on port 19208."""

from __future__ import annotations

import socket
import struct

SYNC = 0x5A
VERSION = 0x01


def pack(api: int, payload: bytes) -> bytes:
    return struct.pack(">BBHIH", SYNC, VERSION, 0, len(payload), api) + b"\x00" * 6 + payload


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(min(1024 * 1024, n - len(buf)))
        if not chunk:
            raise ConnectionError(f"closed after {len(buf)}/{n}")
        buf += chunk
    return buf


class RobodClient:
    def __init__(self, host: str, port: int = 19208) -> None:
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def connect(self) -> None:
        self.close()
        self.sock = socket.create_connection((self.host, self.port), 15)

    def call(self, api: int, payload: bytes, timeout: float) -> tuple[int, bytes]:
        last: Exception | None = None
        for _ in range(3):
            try:
                if self.sock is None:
                    self.connect()
                assert self.sock is not None
                self.sock.settimeout(timeout)
                self.sock.sendall(pack(api, payload))
                header = recv_exact(self.sock, 16)
                sync, ver, _seq, length, res_api = struct.unpack(">BBHIH", header[:10])
                if sync != SYNC or ver != VERSION:
                    raise ConnectionError(f"bad header {header.hex()}")
                body = recv_exact(self.sock, length) if length else b""
                return res_api, body
            except Exception as exc:  # noqa: BLE001
                last = exc
                self.close()
        assert last is not None
        raise last
