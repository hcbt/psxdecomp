#!/usr/bin/env python3
"""Link splat objects with the generated ld scripts and sha1 against originals.

Objects listed under a `/src/` path are compiled from matching C (INCLUDE_ASM
stubs plus any per-function .c that split.py inlined). Everything else is
assembled from splat .s. The C object wins when both exist.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compiler import AS, ASFLAGS, LD, LDFLAGS, OBJCOPY, project_root
import compile as compile_mod

ROOT = project_root()
ASM = ROOT / "asm"
INCLUDE = ROOT / "include"
BUILD = ROOT / "build"
CONFIG = ROOT / "config"
GAME = ROOT / "game"

OBJ_IN_LD = re.compile(r"(build/\S+\.o)")


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def defsyms_from_symbol_addrs() -> list[str]:
    """`--defsym` for symbol_addrs marked absolute:True (outside every splat segment)."""
    path = CONFIG / "symbol_addrs.txt"
    extra: list[str] = []
    if not path.is_file():
        return extra
    for line in path.read_text().splitlines():
        comment = ""
        if "//" in line:
            line, comment = line.split("//", 1)
        if "absolute:True" not in comment.replace(" ", ""):
            continue
        if "=" not in line:
            continue
        name, rhs = line.split("=", 1)
        addr = rhs.split(";")[0].strip()
        extra += ["--defsym", f"{name.strip()}={addr}"]
    return extra


def yaml_target(stem: str) -> Path | None:
    path = CONFIG / f"{stem}.yaml"
    if not path.is_file():
        return None
    for line in path.read_text().splitlines():
        if line.strip().startswith("target_path:"):
            rel = line.split(":", 1)[1].strip()
            return ROOT / rel
    return None


def source_for_object(dest: Path) -> Path | None:
    """Map a splat ld-script object back to a .c (preferred) or .s."""
    dest = dest.resolve()
    try:
        rel = dest.relative_to(BUILD)
    except ValueError:
        rel = Path(*dest.parts)
    parts = rel.parts
    if "src" in parts:
        c_path = ROOT / Path(*parts[parts.index("src") :]).with_suffix(".c")
        if c_path.is_file():
            return c_path
    if "asm" in parts:
        s_path = ROOT / Path(*parts[parts.index("asm") :]).with_suffix(".s")
        if s_path.is_file():
            return s_path
    if dest.name == "header.o":
        candidates = list(ASM.rglob("header.s"))
        if candidates:
            return candidates[0]
    return None


def assemble(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [AS, *ASFLAGS, "-I", str(INCLUDE), "-I", str(ROOT), "-o", str(dest), str(src)],
        check=True,
        capture_output=True,
    )


def build_for_ld(script: Path) -> list[Path]:
    text = script.read_text()
    objs: list[Path] = []
    seen: set[str] = set()
    for match in OBJ_IN_LD.finditer(text):
        rel = match.group(1)
        if rel in seen:
            continue
        seen.add(rel)
        dest = ROOT / rel
        src = source_for_object(dest)
        if src is None:
            raise SystemExit(f"no source for {dest.relative_to(ROOT)}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".c":
            compile_mod.compile_c(src, dest=dest)
        else:
            assemble(src, dest)
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
    build_for_ld(script)
    elf = BUILD / f"{stem}.elf"
    extra: list[str] = []
    extra += defsyms_from_symbol_addrs()
    for name in (
        f"undefined_syms_auto_{stem}.txt",
        f"undefined_funcs_auto_{stem}.txt",
        "undefined_syms_auto.txt",
        "undefined_funcs_auto.txt",
    ):
        path = CONFIG / name
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
    if not match:
        result["reason"] = "sha1"
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
        except SystemExit as exc:
            failed += 1
            print(f"{script.stem}: {exc}")
            continue
        status = "OK" if info.get("match") else f"MISMATCH ({info.get('reason', 'sha1')})"
        print(f"{info['name']}: {status}")
        if not info.get("match"):
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
