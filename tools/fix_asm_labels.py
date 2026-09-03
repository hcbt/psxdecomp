#!/usr/bin/env python3
"""Insert missing splat `.Lxxxxxxxx` labels at the instruction with that VRAM.

spimdisasm can emit a branch to `.L800C2B78` and skip the label itself when
`overlayCategory` on the symbol does not match the function (shared-RAM
overlays). GNU as then leaves an undefined local, and ld fails. Walk splat
comments (`/* off VRAM encoding */`) and define any referenced `.L` that has
no label line yet.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compiler import project_root

ROOT = project_root()
ASM = ROOT / "asm"

LABEL_REF_RE = re.compile(r"(?<![\w.])(\.L[0-9A-Fa-f]{8})\b")
LABEL_DEF_RE = re.compile(r"^\s*(\.L[0-9A-Fa-f]{8})\s*:")
VRAM_RE = re.compile(r"/\*\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\b")
GLABEL_FUNC_RE = re.compile(
    r"^(?:glabel|alabel)\s+((?:fun|func|FUN|FUNC)_[0-9A-Fa-f]{8})\s*$"
)
D_REF_RE = re.compile(r"\bD_([0-9A-Fa-f]{8})\b")
DLABEL_D_RE = re.compile(r"^\s*dlabel\s+D_([0-9A-Fa-f]{8})\s*$")


def _norm(name: str) -> str:
    return ".L" + name[2:].upper()


def referenced(text: str) -> set[str]:
    return {_norm(m) for m in LABEL_REF_RE.findall(text)}


def defined(text: str) -> set[str]:
    return {_norm(m.group(1)) for m in LABEL_DEF_RE.finditer(text)}


def vram_index(lines: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for i, line in enumerate(lines):
        match = VRAM_RE.search(line)
        if match is None:
            continue
        key = ".L" + match.group(1).upper()
        found.setdefault(key, i)
    return found


def fix_text(text: str) -> str:
    missing = referenced(text) - defined(text)
    if not missing:
        return text
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    at = vram_index(lines)
    inserts: list[tuple[int, str]] = []
    for name in missing:
        i = at.get(name)
        if i is None:
            continue
        if i > 0 and LABEL_DEF_RE.match(lines[i - 1]):
            continue
        indent = re.match(r"^(\s*)", lines[i])
        pad = indent.group(1) if indent else ""
        inserts.append((i, f"{pad}{name}:\n"))
    if not inserts:
        return text
    for i, line in sorted(inserts, reverse=True):
        lines.insert(i, line)
    return "".join(lines)


def func_names(asm: Path) -> dict[str, str]:
    """VRAM hex -> glabel name for functions (func_800C264C, fun_8001a968)."""
    found: dict[str, str] = {}
    for path in asm.rglob("*.s"):
        for line in path.read_text(errors="replace").splitlines():
            match = GLABEL_FUNC_RE.match(line)
            if match:
                name = match.group(1)
                found[name.split("_")[-1].upper()] = name
    return found


def dlabel_vrams(asm: Path) -> set[str]:
    found: set[str] = set()
    for path in asm.rglob("*.s"):
        for line in path.read_text(errors="replace").splitlines():
            match = DLABEL_D_RE.match(line)
            if match:
                found.add(match.group(1).upper())
    return found


def rewrite_data_func_refs(text: str, funcs: dict[str, str], skip: set[str]) -> str:
    """Rodata may say D_800C264C + 0x48 when the symbol is glabel func_800C264C."""

    def repl(match: re.Match[str]) -> str:
        vram = match.group(1).upper()
        if vram in skip:
            return match.group(0)
        return funcs.get(vram, match.group(0))

    return D_REF_RE.sub(repl, text)


def fix_all(asm: Path = ASM) -> int:
    """Patch each binary's asm/ independently so shared-RAM overlays do not mix names."""
    if not asm.is_dir():
        return 0
    subs = sorted(p for p in asm.iterdir() if p.is_dir())
    if not subs:
        return fix_tree(asm)
    return sum(fix_tree(sub) for sub in subs)


def fix_tree(asm: Path = ASM) -> int:
    n = 0
    if not asm.is_dir():
        return 0
    funcs = func_names(asm)
    skip = dlabel_vrams(asm)
    for path in sorted(asm.rglob("*.s")):
        original = path.read_text(errors="replace")
        updated = fix_text(original)
        updated = rewrite_data_func_refs(updated, funcs, skip)
        if updated != original:
            path.write_text(updated)
            n += 1
    return n


def main() -> None:
    n = fix_all()
    print(f"patched {n} asm files")


if __name__ == "__main__":
    main()
