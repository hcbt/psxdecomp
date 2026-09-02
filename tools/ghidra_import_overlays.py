#!/usr/bin/env python3
"""Import each overlay BIN into the existing Ghidra project at its load address."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from overlay_table import parse

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"
PROJECT_DIR = ROOT / "ghidra-project"
PROCESSOR = "PSX:LE:32:default"


def project_name() -> str:
    gprs = list(PROJECT_DIR.glob("*.gpr"))
    if not gprs:
        raise SystemExit(f"no .gpr in {PROJECT_DIR}; run ghidra-open first")
    return gprs[0].stem


def main() -> None:
    table = GAME / "OVERLAY.DAT"
    if not table.is_file():
        raise SystemExit(f"missing {table}")
    name = project_name()
    for ov in parse(table, GAME):
        print(f"import {ov.path.name} @ {ov.load:08x}")
        cmd = [
            "ghidra-analyzeHeadless",
            str(PROJECT_DIR),
            name,
            "-import",
            str(ov.path),
            "-processor",
            PROCESSOR,
            "-cspec",
            "default",
            "-loader",
            "BinaryLoader",
            "-loader-baseAddr",
            f"{ov.load:x}",
            "-overwrite",
            "-noanalysis",
        ]
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
