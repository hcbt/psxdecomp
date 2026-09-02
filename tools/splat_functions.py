"""Parse splat asm into per-function expected objects for objdiff."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compiler import AS, ASFLAGS

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "asm"
INCLUDE = ROOT / "include"
OUT_ASM = ROOT / "build" / "expected" / "funcs"
OUT_OBJ = OUT_ASM

LABEL_RE = re.compile(r"^(glabel|alabel)\s+(\S+)\s*$")
STOP_RE = re.compile(
    r"^(glabel|alabel|dlabel|enddlabel|endlabel|nonmatching)\s+"
)
SKIP_NAME = re.compile(r"\.NON_MATCHING$")


@dataclass(frozen=True)
class SplatFunction:
    name: str
    category: str
    size: int
    body: str

    @property
    def key(self) -> str:
        return normalize_symbol(self.name)


def normalize_symbol(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"^(fun|func|FUN|FUNC)_", "", stem)
    return stem.replace("_", "").upper()


def parse_asm_file(path: Path) -> list[SplatFunction]:
    rel = path.relative_to(ASM)
    category = rel.parts[0]
    lines = path.read_text(errors="replace").splitlines(keepends=True)
    found: list[SplatFunction] = []
    i = 0
    while i < len(lines):
        m = LABEL_RE.match(lines[i].rstrip("\n"))
        if not m or SKIP_NAME.search(m.group(2)):
            i += 1
            continue
        name = m.group(2)
        i += 1
        body_lines: list[str] = []
        while i < len(lines):
            raw = lines[i]
            stripped = raw.rstrip("\n")
            if STOP_RE.match(stripped):
                if LABEL_RE.match(stripped) and SKIP_NAME.search(stripped.split()[-1]):
                    i += 1
                    continue
                break
            body_lines.append(raw)
            i += 1
        size = sum(1 for line in body_lines if "/*" in line and "*/" in line) * 4
        if size == 0:
            continue
        found.append(
            SplatFunction(name=name, category=category, size=size, body="".join(body_lines))
        )
    return found


def parse_all() -> list[SplatFunction]:
    if not ASM.is_dir():
        raise SystemExit("no asm/; run splat-split")
    funcs: list[SplatFunction] = []
    for path in sorted(ASM.rglob("*.s")):
        if path.name == "header.s":
            continue
        funcs.extend(parse_asm_file(path))
    return funcs


def _assemble_one(fn: SplatFunction) -> Path:
    dest_s = OUT_ASM / fn.category / f"{fn.name}.s"
    dest_o = dest_s.with_suffix(".o")
    dest_s.parent.mkdir(parents=True, exist_ok=True)
    dest_s.write_text(
        '.include "macro.inc"\n'
        ".set noat\n"
        ".set noreorder\n"
        '.section .text, "ax"\n'
        f".globl {fn.name}\n"
        f"{fn.name}:\n"
        f"{fn.body}"
    )
    proc = subprocess.run(
        [AS, *ASFLAGS, "-I", str(INCLUDE), "-o", str(dest_o), str(dest_s)],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"assemble {fn.name} failed:\n{proc.stderr.decode(errors='replace')}"
        )
    return dest_o


def extract_and_assemble(funcs: list[SplatFunction] | None = None) -> list[SplatFunction]:
    funcs = funcs if funcs is not None else parse_all()
    if OUT_ASM.exists():
        shutil.rmtree(OUT_ASM)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_assemble_one, funcs))
    return funcs
