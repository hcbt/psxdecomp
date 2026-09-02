#!/usr/bin/env python3
"""Generate splat yamls from the disc and split them."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compiler import project_root
import gen_splat

ROOT = project_root()
CONFIG = ROOT / "config"
INCLUDE_ASM = ROOT / "include" / "include_asm.h"


def relativize_include_asm() -> None:
    """splat writes absolute .include paths; those must not land in git."""
    if not INCLUDE_ASM.is_file():
        return
    text = INCLUDE_ASM.read_text()
    abs_inc = (ROOT / "include").resolve().as_posix()
    new = text.replace(f'"{abs_inc}/macro.inc"', '"macro.inc"').replace(
        f'"{abs_inc}/labels.inc"', '"labels.inc"'
    )
    if new != text:
        INCLUDE_ASM.write_text(new)


def main() -> None:
    gen_splat.main()
    yamls = sorted(p for p in CONFIG.glob("*.yaml") if p.is_file())
    if not yamls:
        raise SystemExit(f"no splat yamls in {CONFIG}")
    for yaml in yamls:
        subprocess.run(["splat", "split", str(yaml)], check=True)
    relativize_include_asm()


if __name__ == "__main__":
    main()
