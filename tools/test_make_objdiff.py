#!/usr/bin/env python3
"""collect_units includes splat data/rodata and skips full TU .text objects."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_objdiff import collect_units


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_data_units_with_funcs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        touch(root / "build/expected/funcs/eng/func_80051F44.o")
        touch(root / "build/src/funcs/func_80051F44.o")
        touch(root / "build/expected/eng/data/data.data.o")
        touch(root / "build/expected/eng/data/rodata.rodata.o")
        touch(root / "build/expected/eng/eng.o")
        touch(root / "build/expected/eng/header.o")
        units, categories = collect_units(root)
        names = {u["name"]: u for u in units}
        assert set(names) == {
            "eng/func_80051F44",
            "eng/data/data.data",
            "eng/data/rodata.rodata",
        }, set(names)
        assert names["eng/func_80051F44"]["base_path"] == "build/src/funcs/func_80051F44.o"
        assert "base_path" not in names["eng/data/data.data"]
        assert categories == {"eng": "eng"}
    print("ok data_units_with_funcs")


def test_full_objects_without_funcs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        touch(root / "build/expected/eng/data/data.data.o")
        touch(root / "build/expected/eng/eng.o")
        units, _ = collect_units(root)
        names = {u["name"] for u in units}
        assert names == {"eng/data/data.data", "eng/eng"}, names
    print("ok full_objects_without_funcs")


if __name__ == "__main__":
    test_data_units_with_funcs()
    test_full_objects_without_funcs()
