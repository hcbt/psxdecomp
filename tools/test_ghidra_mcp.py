#!/usr/bin/env python3
"""ghidra_mcp port/HTTP probes (no Ghidra GUI)."""

from __future__ import annotations

import http.server
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
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


if __name__ == "__main__":
    test_port_open_false()
    test_mcp_http_up()
