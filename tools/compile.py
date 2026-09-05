#!/usr/bin/env python3
"""Compile matching C with the old cc1 + maspsx pipeline."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compiler import ASPSX_VER, AS, ASFLAGS, CC1, CFLAGS, CPP, MASPSX, project_root

ROOT = project_root()
SRC = ROOT / "src"
OUT = ROOT / "build" / "src"
INCLUDE = ROOT / "include"
TOOLKIT_DIR = Path(__file__).resolve().parent

ASM_TOKEN_RE = re.compile(
    r"\b__asm(?:__)?\b|\basm\s*(?:(?:__)?volatile(?:__)?\s*)?\("
)


def psyq_include() -> Path | None:
    for candidate in (
        ROOT / "tools" / "psyq" / "include",
        TOOLKIT_DIR / "psyq" / "include",
    ):
        if candidate.is_dir():
            return candidate
    return None


def strip_c_comments(text: str) -> str:
    """Drop // and /* */ comments; keep string contents."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("//", i):
            nl = text.find("\n", i)
            if nl < 0:
                break
            i = nl
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                break
            i = end + 2
            continue
        ch = text[i]
        if ch in "\"'":
            out.append(ch)
            i += 1
            while i < n:
                out.append(text[i])
                if text[i] == "\\":
                    i += 1
                    if i < n:
                        out.append(text[i])
                        i += 1
                    continue
                if text[i] == ch:
                    i += 1
                    break
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def is_splat_tu(path: Path) -> bool:
    """splat TUs pull unmatched functions via INCLUDE_ASM; objdiff wants per-fn .c."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return False
    return "INCLUDE_ASM(" in text


def listing_wrapper_reason(path: Path) -> str | None:
    """If this per-function .c is GNU asm instead of C, return an error string."""
    if is_splat_tu(path):
        return None
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return None
    if ASM_TOKEN_RE.search(strip_c_comments(text)) is None:
        return None
    try:
        shown = path.resolve().relative_to(ROOT)
    except ValueError:
        shown = path
    return (
        f"listing wrapper: {shown} uses __asm__; write C. "
        "INCLUDE_ASM is the unmatched form."
    )


def compile_c(src: Path, src_root: Path = SRC, dest: Path | None = None) -> Path:
    src = src.resolve()
    reason = listing_wrapper_reason(src)
    if reason:
        raise SystemExit(reason)
    if dest is None:
        rel = src.relative_to(src_root) if src.is_relative_to(src_root) else Path(src.name)
        dest = OUT / rel.with_suffix(".o")
    else:
        dest = dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    asm = dest.with_suffix(".s")
    cpp_cmd = [CPP, "-P", "-I", str(INCLUDE), "-I", str(src.parent)]
    inc = psyq_include()
    if inc is not None:
        cpp_cmd += ["-I", str(inc)]
    cpp_cmd.append(str(src))
    preprocessed = subprocess.run(
        cpp_cmd, check=True, capture_output=True, stdin=subprocess.DEVNULL
    )
    i_file = dest.with_suffix(".i")
    i_file.write_bytes(preprocessed.stdout)
    subprocess.run(
        [CC1, "-quiet", *CFLAGS, "-o", str(asm), str(i_file)],
        check=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            MASPSX,
            f"--aspsx-version={ASPSX_VER}",
            "--run-assembler",
            f"--gnu-as-path={AS}",
            *ASFLAGS,
            "-I",
            str(INCLUDE),
            "-I",
            str(ROOT),
            "-o",
            str(dest),
            str(asm),
        ],
        check=True,
        stdin=subprocess.DEVNULL,
    )
    try:
        print(dest.relative_to(ROOT))
    except ValueError:
        print(dest)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=SRC, help="root of matching C")
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()
    src_root = args.src.resolve()
    files = [p.resolve() for p in args.files]
    explicit = bool(args.files)
    if not files:
        files = sorted(src_root.rglob("*.c")) if src_root.is_dir() else []
    if not files:
        raise SystemExit("no .c files (pass paths or put them under src/)")
    skipped = 0
    for src in files:
        reason = listing_wrapper_reason(src)
        if reason:
            if explicit:
                raise SystemExit(reason)
            skipped += 1
            continue
        compile_c(src, src_root=src_root)
    if skipped:
        print(f"skipped {skipped} listing wrappers", file=sys.stderr)


if __name__ == "__main__":
    main()
