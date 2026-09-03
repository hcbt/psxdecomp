#!/usr/bin/env python3
"""ghidra_mcp port/HTTP probes and relaunch (no Ghidra GUI)."""

from __future__ import annotations

import http.server
import socket
import sys
import threading
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import ghidra_mcp
from ghidra_mcp import mcp_http_up, port_open


def test_port_open_false() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        unused = sock.getsockname()[1]
    assert port_open("127.0.0.1", unused) is False
    print("ok port_closed")


def test_mcp_http_up() -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_error(406, "use POST")

        def log_message(self, *_args: object) -> None:
            return

    httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        assert port_open("127.0.0.1", port) is True
        assert mcp_http_up(f"http://127.0.0.1:{port}/mcp") is True
    finally:
        httpd.shutdown()
    print("ok mcp_http_up")


def test_ensure_starts_when_down() -> None:
    started = []

    def fake_http() -> bool:
        return bool(started)

    def fake_start() -> None:
        started.append(True)

    with (
        patch.object(ghidra_mcp, "mcp_http_up", fake_http),
        patch.object(ghidra_mcp, "port_open", return_value=False),
        patch.object(ghidra_mcp, "start_ghidra_open", fake_start),
        patch.object(ghidra_mcp, "POLL_S", 0),
    ):
        ghidra_mcp.ensure_ghidra(wait_s=1)
    assert started == [True]
    print("ok ensure_starts_when_down")


def test_watch_relaunches_after_drop() -> None:
    http_up = [True]
    started = []
    stop = threading.Event()

    def fake_http() -> bool:
        return http_up[0]

    def fake_start() -> None:
        started.append(True)
        http_up[0] = True
        stop.set()

    with (
        patch.object(ghidra_mcp, "mcp_http_up", fake_http),
        patch.object(ghidra_mcp, "port_open", return_value=False),
        patch.object(ghidra_mcp, "start_ghidra_open", fake_start),
        patch.object(ghidra_mcp, "POLL_S", 0),
    ):
        thread = threading.Thread(
            target=ghidra_mcp.watch_ghidra, kwargs={"stop": stop, "interval": 0.01}
        )
        thread.start()
        http_up[0] = False
        thread.join(timeout=2)
    assert stop.is_set()
    assert started == [True]
    print("ok watch_relaunches_after_drop")


if __name__ == "__main__":
    test_port_open_false()
    test_mcp_http_up()
    test_ensure_starts_when_down()
    test_watch_relaunches_after_drop()
