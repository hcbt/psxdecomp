#!/usr/bin/env python3
"""Write objdiff.json pairing splat function objects with rebuilt src objects.

Per-function .text lives under build/expected/funcs/. splat .data / .rodata
objects live under build/expected/<tu>/data/. Full TU .o files (eng.o, main.o)
duplicate the per-function .text and are omitted when funcs/<tu>/ exists.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compiler import project_root

FUNCS_REL = Path("build") / "expected" / "funcs"
SRC_FUNCS_REL = Path("build") / "src" / "funcs"
EXPECTED_REL = Path("build") / "expected"


def _under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def collect_units(root: Path) -> tuple[list[dict], dict[str, str]]:
    """Return (units, category_id -> name) for an objdiff.json."""
    root = root.resolve()
    funcs = root / FUNCS_REL
    src_funcs = root / SRC_FUNCS_REL
    expected = root / EXPECTED_REL
    units: list[dict] = []
    categories: dict[str, str] = {}

    def add(
        name: str,
        target: Path,
        category: str,
        base: Path | None = None,
    ) -> None:
        categories.setdefault(category, category)
        unit: dict = {
            "name": name,
            "target_path": str(target.relative_to(root)).replace("\\", "/"),
            "metadata": {"progress_categories": [category]},
        }
        if base is not None and base.is_file():
            unit["base_path"] = str(base.relative_to(root)).replace("\\", "/")
        units.append(unit)

    if funcs.is_dir():
        for obj in sorted(funcs.rglob("*.o")):
            rel = obj.relative_to(funcs)
            if len(rel.parts) < 2:
                continue
            category = rel.parts[0]
            add(
                str(rel.with_suffix("")).replace("\\", "/"),
                obj,
                category,
                src_funcs / f"{obj.stem}.o",
            )

    if expected.is_dir():
        for obj in sorted(expected.rglob("*.o")):
            if _under(obj, funcs):
                continue
            rel = obj.relative_to(expected)
            if rel.name == "header.o" or len(rel.parts) < 2:
                continue
            category = rel.parts[0]
            # Per-function units already cover .text. Keep splat data/rodata.
            if (funcs / category).is_dir() and "data" not in rel.parts:
                continue
            add(str(rel.with_suffix("")).replace("\\", "/"), obj, category)

    return units, categories


def write_config(root: Path, units: list[dict], categories: dict[str, str]) -> Path:
    cfg = {
        "custom_make": "true",
        "build_target": False,
        "build_base": False,
        "progress_categories": [
            {"id": cid, "name": name} for cid, name in sorted(categories.items())
        ],
        "units": units,
    }
    path = root / "objdiff.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    return path


def main() -> None:
    root = project_root()
    units, categories = collect_units(root)
    path = write_config(root, units, categories)
    print(f"wrote {path.name} ({len(units)} units)")


if __name__ == "__main__":
    main()
