#!/usr/bin/env python3
"""Generate splat yamls from the disc and split them."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compiler import project_root
from splat_functions import normalize_symbol
import gen_splat

ROOT = project_root()
CONFIG = ROOT / "config"
SRC = ROOT / "src"
INCLUDE = ROOT / "include"

COMMON_H = """\
#ifndef COMMON_H
#define COMMON_H

#include "include_asm.h"

#endif
"""

INCLUDE_MACRO_RE = re.compile(
    r'(INCLUDE_(?:ASM|RODATA)\(")([^"]+)(")'
)
INCLUDE_ASM_STMT_RE = re.compile(
    r'INCLUDE_ASM\("([^"]+)",\s*([A-Za-z0-9_]+)\)\s*;'
)


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


def ensure_common_h() -> None:
    INCLUDE.mkdir(exist_ok=True)
    path = INCLUDE / "common.h"
    if not path.exists():
        path.write_text(COMMON_H)


def relativize_include_macros(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        folder = match.group(2)
        path = Path(folder)
        if path.is_absolute():
            try:
                folder = path.resolve().relative_to(ROOT).as_posix()
            except ValueError:
                pass
        return f"{match.group(1)}{folder}{match.group(3)}"

    return INCLUDE_MACRO_RE.sub(repl, text)


def matching_c(src_dir: Path, name: str, tu: Path) -> Path | None:
    tu_res = tu.resolve()
    exact = src_dir / f"{name}.c"
    if exact.is_file() and exact.resolve() != tu_res:
        return exact
    key = normalize_symbol(name)
    for path in sorted(src_dir.glob("*.c")):
        if path.resolve() == tu_res:
            continue
        if normalize_symbol(path.stem) == key:
            return path
    return None


def inject_matched_c(text: str, c_path: Path) -> str:
    src_dir = c_path.parent

    def repl(match: re.Match[str]) -> str:
        found = matching_c(src_dir, match.group(2), c_path)
        if found is None:
            return match.group(0)
        return f'#include "{found.name}"'

    return INCLUDE_ASM_STMT_RE.sub(repl, text)


def patch_generated_c() -> None:
    if not SRC.is_dir():
        return
    for path in SRC.rglob("*.c"):
        original = path.read_text()
        if "INCLUDE_ASM(" not in original and "INCLUDE_RODATA(" not in original:
            continue
        text = inject_matched_c(relativize_include_macros(original), path)
        if text != original:
            path.write_text(text)


def splat_one(yaml: Path) -> None:
    _relative_include_asm_write()
    from splat.scripts.split import main as splat_split

    splat_split([yaml], modes=None, verbose=False, use_cache=False)


def main() -> None:
    ensure_common_h()
    gen_splat.main()
    asm = ROOT / "asm"
    if asm.is_dir():
        shutil.rmtree(asm)
    yamls = sorted(p for p in CONFIG.glob("*.yaml") if p.is_file())
    if not yamls:
        raise SystemExit(f"no splat yamls in {CONFIG}")
    self = Path(__file__).resolve()
    for yaml in yamls:
        subprocess.run([sys.executable, str(self), "--splat", str(yaml)], check=True)
    patch_generated_c()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--splat":
        splat_one(Path(sys.argv[2]))
    else:
        main()
