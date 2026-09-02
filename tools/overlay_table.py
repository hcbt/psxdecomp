#!/usr/bin/env python3
"""Read a PS1 overlay table (0x30-byte records: name, load, size)."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

RECORD = 0x30


@dataclass(frozen=True)
class Overlay:
    name: str
    path: Path
    load: int
    size: int


def parse(table: Path, game_dir: Path) -> list[Overlay]:
    data = table.read_bytes()
    overlays: list[Overlay] = []
    for off in range(0, len(data), RECORD):
        rec = data[off : off + RECORD]
        if len(rec) < RECORD or rec[0] == 0:
            break
        raw = rec[:16].split(b"\0", 1)[0].decode("ascii", "replace")
        name = raw.replace("\\", "/").split("/")[-1].split(";")[0]
        if not name:
            continue
        load, size = struct.unpack_from("<II", rec, 0x20)
        path = game_dir / name
        if path.is_file():
            overlays.append(Overlay(name, path, load, size))
    return overlays
