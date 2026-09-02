#!/usr/bin/env python3
"""Write objdiff.json pairing splat function objects with rebuilt src objects."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNCS = ROOT / "build" / "expected" / "funcs"
SRC_FUNCS = ROOT / "build" / "src" / "funcs"
EXPECTED = ROOT / "build" / "expected"


def main() -> None:
    units = []
    categories: dict[str, str] = {}
    if FUNCS.is_dir():
        for obj in sorted(FUNCS.rglob("*.o")):
            rel = obj.relative_to(FUNCS)
            if len(rel.parts) < 2:
                continue
            category = rel.parts[0]
            categories.setdefault(category, category)
            name = obj.stem
            base = SRC_FUNCS / f"{name}.o"
            unit = {
                "name": str(rel.with_suffix("")).replace("\\", "/"),
                "target_path": str(obj.relative_to(ROOT)),
                "metadata": {"progress_categories": [category]},
            }
            if base.is_file():
                unit["base_path"] = str(base.relative_to(ROOT))
            units.append(unit)
    if EXPECTED.is_dir():
        for obj in sorted(EXPECTED.rglob("*.o")):
            try:
                obj.relative_to(FUNCS)
                continue
            except ValueError:
                pass
            rel = obj.relative_to(EXPECTED)
            if rel.name == "header.o" or len(rel.parts) < 2:
                continue
            category = rel.parts[0]
            if (FUNCS / category).is_dir():
                continue
            categories.setdefault(category, category)
            unit = {
                "name": str(rel.with_suffix("")).replace("\\", "/"),
                "target_path": str(obj.relative_to(ROOT)),
                "metadata": {"progress_categories": [category]},
            }
            units.append(unit)
    cfg = {
        "custom_make": "true",
        "build_target": False,
        "build_base": False,
        "progress_categories": [
            {"id": cid, "name": name} for cid, name in sorted(categories.items())
        ],
        "units": units,
    }
    path = ROOT / "objdiff.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"wrote {path.name} ({len(units)} units)")


if __name__ == "__main__":
    main()
