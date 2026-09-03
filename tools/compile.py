#!/usr/bin/env python3
"""Compile matching C with the old cc1 + maspsx pipeline."""

from __future__ import annotations

import argparse
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


def psyq_include() -> Path | None:
    for candidate in (
        ROOT / "tools" / "psyq" / "include",
        TOOLKIT_DIR / "psyq" / "include",
    ):
        if candidate.is_dir():
            return candidate
    return None


def compile_c(src: Path, src_root: Path = SRC, dest: Path | None = None) -> Path:
    src = src.resolve()
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
    preprocessed = subprocess.run(cpp_cmd, check=True, capture_output=True)
    i_file = dest.with_suffix(".i")
    i_file.write_bytes(preprocessed.stdout)
    subprocess.run([CC1, "-quiet", *CFLAGS, "-o", str(asm), str(i_file)], check=True)
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
    if not files:
        files = sorted(src_root.rglob("*.c")) if src_root.is_dir() else []
    if not files:
        raise SystemExit("no .c files (pass paths or put them under src/)")
    for src in files:
        compile_c(src, src_root=src_root)


if __name__ == "__main__":
    main()
