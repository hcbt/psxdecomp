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


def main() -> None:
    gen_splat.main()
    yamls = sorted(p for p in CONFIG.glob("*.yaml") if p.is_file())
    if not yamls:
        raise SystemExit(f"no splat yamls in {CONFIG}")
    for yaml in yamls:
        subprocess.run(["splat", "split", str(yaml)], check=True)


if __name__ == "__main__":
    main()
