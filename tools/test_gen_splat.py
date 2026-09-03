#!/usr/bin/env python3
"""Synthetic checks for find_text_range (no disc dump required)."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gen_splat import find_text_range, format_subsegments


def word(value: int) -> bytes:
    return struct.pack("<I", value)


def test_find_text_range() -> None:
    rodata = b"OVERLAY.DAT\x00\x00\x00\x00\x00" + b"\x00" * 16
    # two jr $ra stubs, then two stack-frame functions, then data
    stubs = word(0x03E00008) + word(0x00001021) + word(0x03E00008) + word(0x00001021)
    fn1 = word(0x27BDFFE8) + word(0xAFBF0010) + word(0x03E00008) + word(0x27BD0018)
    pad = word(0x27BDFFD0) + word(0xAFBF0028) + word(0x03E00008) + word(0x27BD0030)
    data = b"hello world\x00\x00\x00\x00"
    payload = rodata + stubs + fn1 + pad + data
    found = find_text_range(payload)
    assert found is not None, "expected a .text range"
    start, end = found
    assert start == len(rodata), (hex(start), hex(len(rodata)))
    assert end == len(rodata) + len(stubs) + len(fn1) + len(pad), (hex(end), len(payload))
    yaml = format_subsegments(0x800, payload, "main", text_type="c")
    assert "rodata, rodata" in yaml
    assert ", c, main" in yaml
    assert "data, data" in yaml
    print("ok", yaml)


if __name__ == "__main__":
    test_find_text_range()
