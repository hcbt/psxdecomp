#!/usr/bin/env python3
"""Link splat objects with the generated ld scripts and sha1 against originals."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compiler import AS, ASFLAGS, LD, LDFLAGS, OBJCOPY

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "asm"
INCLUDE = ROOT / "include"
BUILD = ROOT / "build"
CONFIG = ROOT / "config"
GAME = ROOT / "game"

OBJ_IN_LD = re.compile(r"(build/\S+\.o)")


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def yaml_target(stem: str) -> Path | None:
    path = CONFIG / f"{stem}.yaml"
    if not path.is_file():
        return None
    for line in path.read_text().splitlines():
        if line.strip().startswith("target_path:"):
            rel = line.split(":", 1)[1].strip()
            return ROOT / rel
    return None


def assemble_for_ld(script: Path) -> list[Path]:
    text = script.read_text()
    objs = []
    for match in OBJ_IN_LD.finditer(text):
        dest = ROOT / match.group(1)
        if dest.name == "header.o":
            src = ASM / dest.parent.name / "header.s"
            if not src.is_file():
                # splat: asm/<basename>/header.s
                candidates = list(ASM.rglob("header.s"))
                src = candidates[0] if candidates else src
        else:
            # build/<bin>/asm/<bin>/main.o -> asm/<bin>/main.s
            rel_asm = Path(*dest.parts[dest.parts.index("asm") :])
            src = ROOT / rel_asm.with_suffix(".s")
        if not src.is_file():
            raise SystemExit(f"no splat asm for {dest}: expected {src}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [AS, *ASFLAGS, "-I", str(INCLUDE), "-o", str(dest), str(src)],
            check=True,
            capture_output=True,
        )
        objs.append(dest)
    return objs


def linked_bytes(elf: Path) -> bytes:
    raw = elf.with_suffix(".bin")
    subprocess.run([OBJCOPY, "-O", "binary", str(elf), str(raw)], check=True)
    return raw.read_bytes()


def original_payload(target: Path) -> bytes:
    return target.read_bytes()


def link_one(script: Path) -> dict:
    stem = script.stem
    assemble_for_ld(script)
    elf = BUILD / f"{stem}.elf"
    extra = []
    for name in ("undefined_syms_auto.txt", "undefined_funcs_auto.txt"):
        path = ROOT / name
        if path.is_file() and path.stat().st_size:
            extra += ["-T", str(path)]
    subprocess.run(
        [LD, *LDFLAGS, *extra, "-T", str(script), "-o", str(elf)],
        check=True,
        capture_output=True,
    )
    target = yaml_target(stem)
    result = {"name": stem, "elf": str(elf.relative_to(ROOT)), "linked": True}
    if target is None or not target.is_file():
        result["match"] = False
        result["reason"] = "no original binary"
        return result
    got = linked_bytes(elf)
    want = original_payload(target)
    # Linked binary may be padded to section alignment.
    if len(got) < len(want):
        result["match"] = False
        result["reason"] = f"linked {len(got)} < original {len(want)}"
        return result
    match = got[: len(want)] == want
    result["match"] = match
    result["sha1_original"] = sha1(want)
    result["sha1_linked"] = sha1(got[: len(want)])
    return result


def main() -> int:
    scripts = sorted(BUILD.glob("*.ld"))
    if not scripts:
        raise SystemExit("no build/*.ld; run splat-split")
    failed = 0
    for script in scripts:
        try:
            info = link_one(script)
        except subprocess.CalledProcessError as exc:
            failed += 1
            err = (exc.stderr or b"").decode(errors="replace")[-400:]
            print(f"{script.stem}: link failed\n{err}")
            continue
        status = "OK" if info.get("match") else f"MISMATCH ({info.get('reason', 'sha1')})"
        print(f"{info['name']}: {status}")
        if not info.get("match"):
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
