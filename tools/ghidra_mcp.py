#!/usr/bin/env python3
"""Start Ghidra if needed, then stdio-proxy its streamable HTTP MCP.

MCP clients spawn this as a stdio server. Handshake waits until
http://127.0.0.1:8080/mcp answers. If Ghidra is closed later, this
process starts ghidra-open again instead of leaving inspect dead.
Logs go to stderr; stdout is MCP only.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8080
MCP_URL = f"http://{HOST}:{PORT}/mcp"
WAIT_S = 180
POLL_S = 0.5
WATCH_S = 2.0

_start_lock = threading.Lock()


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def port_open(host: str = HOST, port: int = PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def mcp_http_up(url: str = MCP_URL) -> bool:
    """True once anything HTTP is speaking on the MCP path (including 4xx)."""
    req = urllib.request.Request(url, method="GET")
    try:
        urllib.request.urlopen(req, timeout=1)
        return True
    except urllib.error.HTTPError:
        return True
    except OSError:
        return False


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def start_ghidra_open() -> None:
    ghidra_open = shutil_which("ghidra-open")
    if ghidra_open is None:
        raise SystemExit("ghidra-open is not on PATH; run via devenv shell -- ghidra-mcp")
    state = Path(os.environ.get("DEVENV_STATE") or "/tmp")
    state.mkdir(parents=True, exist_ok=True)
    log_path = state / "ghidra-open.log"
    log(f"starting ghidra-open (log {log_path})")
    subprocess.Popen(
        [ghidra_open],
        stdout=log_path.open("ab"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=os.environ.get("DEVENV_ROOT") or os.getcwd(),
    )


def ensure_ghidra(wait_s: float = WAIT_S) -> None:
    with _start_lock:
        if mcp_http_up():
            return
        if not port_open():
            start_ghidra_open()
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            if mcp_http_up():
                log(f"Ghidra MCP ready at {MCP_URL}")
                return
            time.sleep(POLL_S)
        raise SystemExit(f"Ghidra MCP did not answer at {MCP_URL} within {wait_s:.0f}s")


def watch_ghidra(stop: threading.Event | None = None, interval: float = WATCH_S) -> None:
    """Relaunch Ghidra when the HTTP MCP goes away (window closed)."""
    while True:
        if stop is not None:
            if stop.wait(interval):
                return
        else:
            time.sleep(interval)
        if mcp_http_up():
            continue
        log("Ghidra MCP gone; starting ghidra-open")
        try:
            ensure_ghidra()
        except SystemExit as exc:
            log(str(exc))


def run_proxy() -> int:
    proxy = shutil_which("mcp-proxy")
    if proxy is None:
        raise SystemExit("mcp-proxy is not on PATH; add it to the project pyproject.toml")
    return subprocess.call([proxy, "--transport", "streamablehttp", MCP_URL])


def main() -> None:
    ensure_ghidra()
    threading.Thread(target=watch_ghidra, name="ghidra-watch", daemon=True).start()
    raise SystemExit(run_proxy())


if __name__ == "__main__":
    main()
