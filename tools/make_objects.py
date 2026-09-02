#!/usr/bin/env python3
"""Assemble splat .s files into build/expected/ for objdiff."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compiler import AS, ASFLAGS, project_root

ROOT = project_root()
ASM = ROOT / "asm"
HANDWRITTEN = ROOT / "expected"
OUT = ROOT / "build" / "expected"


def assemble(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [AS, *ASFLAGS, "-I", str(ROOT / "include"), "-o", str(dest), str(src)]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    n = 0
    if ASM.is_dir():
        for src in ASM.rglob("*.s"):
            if src.name == "header.s":
                continue
            assemble(src, OUT / src.relative_to(ASM).with_suffix(".o"))
            n += 1
    if HANDWRITTEN.is_dir():
        for src in HANDWRITTEN.rglob("*.s"):
            assemble(src, OUT / src.relative_to(HANDWRITTEN).with_suffix(".o"))
            n += 1
    if n == 0:
        raise SystemExit("no .s files under asm/ or expected/; run splat-split")
    print(f"assembled {n} objects into {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
