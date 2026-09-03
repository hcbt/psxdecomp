#!/usr/bin/env python3
"""cpp/cc1/maspsx must not hang when stdin is a pipe that never EOFs."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

TIMEOUT_S = 5


def run_with_never_eof_pipe(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    """stdin is a pipe we never write to and never close (agent stdio)."""
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        proc.wait(timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise AssertionError(f"hung on stdin ({TIMEOUT_S}s): {cmd}") from None
    stdout, stderr = proc.communicate()
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def test_cpp_with_file() -> None:
    cpp = shutil.which("cpp-2.8.1-psx")
    if cpp is None:
        raise SystemExit("cpp-2.8.1-psx not on PATH")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "t.c"
        out = Path(tmp) / "t.i"
        src.write_text("int x;\n")
        proc = run_with_never_eof_pipe([cpp, "-P", str(src), "-o", str(out)])
        assert proc.returncode == 0, proc.stderr.decode(errors="replace")
        assert "int x" in out.read_text()
    print("ok cpp_with_file")


def test_cpp_glued_dash_p_fails_fast() -> None:
    """`cpp -Ptest.c` is one argv; without a wrapper this read stdin forever."""
    cpp = shutil.which("cpp-2.8.1-psx")
    if cpp is None:
        raise SystemExit("cpp-2.8.1-psx not on PATH")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "t.i"
        proc = run_with_never_eof_pipe([cpp, "-Ptest.c", "-o", str(out)])
        assert proc.returncode != 0 or not out.exists() or out.stat().st_size == 0
    print("ok cpp_glued_dash_p_fails_fast")


def test_cc1_with_file() -> None:
    cc1 = shutil.which("cc1-2.8.1-psx")
    if cc1 is None:
        raise SystemExit("cc1-2.8.1-psx not on PATH")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "t.i"
        out = Path(tmp) / "t.s"
        src.write_text("int x;\n")
        proc = run_with_never_eof_pipe([cc1, "-quiet", "-O2", "-G0", "-o", str(out), str(src)])
        assert proc.returncode == 0, proc.stderr.decode(errors="replace")
        assert out.stat().st_size > 0
    print("ok cc1_with_file")


def test_maspsx_file_no_stdin_warning() -> None:
    maspsx = shutil.which("maspsx")
    if maspsx is None:
        raise SystemExit("maspsx not on PATH")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "t.s"
        src.write_text("nop\n")
        proc = run_with_never_eof_pipe([maspsx, str(src)])
        err = proc.stderr.decode(errors="replace")
        assert "no input from stdin" not in err, err
        assert proc.returncode == 0, err
    print("ok maspsx_file_no_stdin_warning")


if __name__ == "__main__":
    test_cpp_with_file()
    test_cpp_glued_dash_p_fails_fast()
    test_cc1_with_file()
    test_maspsx_file_no_stdin_warning()
