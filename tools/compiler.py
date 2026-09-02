"""Matching-compiler defaults.

Proven on one leaf. Do not treat these as game-wide until more leaves match.

Project data (src, game, build) lives in DEVENV_ROOT so this toolkit can be
imported into another devenv. Tools live next to this file.
"""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    env = os.environ.get("DEVENV_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1]

CC1 = "cc1-2.8.1-psx"
CPP = "cpp-2.8.1-psx"
ASPSX_VER = "2.79"
CFLAGS = ["-O2", "-G0", "-fno-schedule-insns"]
# Host `as` is Clang on macOS. Always the mipsel GNU assembler.
AS = "mipsel-linux-gnu-as"
# r4000 so splat `tge` is accepted (ASPSX emits it on R3000 too).
ASFLAGS = ["-EL", "-march=r4000", "-no-pad-sections"]
LD = "mipsel-linux-gnu-ld"
LDFLAGS = ["-EL"]
OBJCOPY = "mipsel-linux-gnu-objcopy"
MASPSX = "maspsx"
