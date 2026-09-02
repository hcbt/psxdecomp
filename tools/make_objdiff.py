#!/usr/bin/env python3
"""Write objdiff.json pairing expected (splat asm) objects with rebuilt src objects."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "build" / "expected"
SRC_BUILD = ROOT / "build" / "src"


def main() -> None:
    units = []
    if not EXPECTED.is_dir():
        raise SystemExit("no build/expected/; run make objects")
    for obj in sorted(EXPECTED.rglob("*.o")):
        rel = obj.relative_to(EXPECTED)
        base = SRC_BUILD / rel
        units.append(
            {
                "name": str(rel.with_suffix("")).replace("\\", "/"),
                "target_path": str(obj.relative_to(ROOT)),
                "base_path": str(base.relative_to(ROOT)),
            }
        )
    cfg = {
        "custom_make": "make",
        "custom_args": ["objects"],
        "build_target": False,
        "units": units,
    }
    path = ROOT / "objdiff.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"wrote {path.name} ({len(units)} units)")


if __name__ == "__main__":
    main()
