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


def _relative_include_asm_write() -> None:
    """splat embeds an absolute generated_asm_macros_directory in include_asm.h."""
    from splat.util import file_presets

    orig = file_presets._write

    def _write(filepath: str, contents: str) -> None:
        if Path(filepath).name == "include_asm.h":
            parent = Path(filepath).resolve().parent.as_posix()
            contents = contents.replace(f"{parent}/macro.inc", "macro.inc")
            contents = contents.replace(f"{parent}/labels.inc", "labels.inc")
        orig(filepath, contents)

    file_presets._write = _write


def splat_one(yaml: Path) -> None:
    _relative_include_asm_write()
    from splat.scripts.split import main as splat_split

    splat_split([yaml], modes=None, verbose=False, use_cache=False)


def main() -> None:
    gen_splat.main()
    yamls = sorted(p for p in CONFIG.glob("*.yaml") if p.is_file())
    if not yamls:
        raise SystemExit(f"no splat yamls in {CONFIG}")
    self = Path(__file__).resolve()
    for yaml in yamls:
        subprocess.run([sys.executable, str(self), "--splat", str(yaml)], check=True)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--splat":
        splat_one(Path(sys.argv[2]))
    else:
        main()
