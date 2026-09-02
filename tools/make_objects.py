#!/usr/bin/env python3
"""Assemble splat .s files into build/expected/ for objdiff."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "asm"
OUT = ROOT / "build" / "expected"
# Host `AS` is often Clang's as on macOS. Always use the mipsel GNU assembler.
AS = "mipsel-linux-gnu-as"
# r4000 so `tge` in splat output is accepted (R3000 aspsx emits it anyway).
ASFLAGS = "-EL -march=r4000 -no-pad-sections".split()


def main() -> None:
    if not ASM.is_dir():
        raise SystemExit("no asm/; run make split")
    n = 0
    for src in ASM.rglob("*.s"):
        if src.name == "header.s":
            continue
        rel = src.relative_to(ASM).with_suffix(".o")
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = [AS, *ASFLAGS, "-I", str(ROOT / "include"), "-o", str(dest), str(src)]
        print(" ".join(cmd))
        subprocess.run(cmd, check=True)
        n += 1
    if n == 0:
        raise SystemExit("no .s files under asm/")
    print(f"assembled {n} objects into {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
