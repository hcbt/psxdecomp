#!/usr/bin/env python3
"""Write splat yamls for the boot EXE and every overlay that exists on disc."""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from overlay_table import parse  # noqa: E402

GAME = ROOT / "game"
CONFIG = ROOT / "config"


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    h.update(path.read_bytes())
    return h.hexdigest()


def boot_exe() -> Path:
    cnf = GAME / "SYSTEM.CNF"
    if cnf.is_file():
        for line in cnf.read_text(errors="replace").replace("\r", "").splitlines():
            if line.upper().startswith("BOOT="):
                name = line.split("=", 1)[1].replace("\\", "/").split("/")[-1].split(";")[0]
                path = GAME / name
                if path.is_file():
                    return path
    for path in sorted(GAME.iterdir()):
        if path.is_file() and path.read_bytes()[:8] == b"PS-X EXE":
            return path
    raise SystemExit(f"no PS-X EXE in {GAME}")


def splat_common(name: str, target: Path, basename: str) -> str:
    return f"""name: {name}
sha1: {sha1(target)}
options:
  basename: {basename}
  target_path: {target.relative_to(ROOT)}
  elf_path: build/{basename}.elf
  base_path: ..
  platform: psx
  compiler: PSYQ
  asm_path: asm/{basename}
  src_path: src/{basename}
  build_path: build/{basename}
  ld_script_path: build/{basename}.ld
  ld_dependencies: True
  find_file_boundaries: True
  o_as_suffix: True
  use_legacy_include_asm: False
  section_order: [".rodata", ".text", ".data", ".bss"]
  ld_bss_is_noload: False
  symbol_addrs_path:
    - symbol_addrs.txt
  reloc_addrs_path:
    - reloc_addrs.txt
  subalign: 4
  string_encoding: ASCII
  data_string_encoding: ASCII
"""


def write_exe(exe: Path) -> Path:
    data = exe.read_bytes()
    dest, text_size = struct.unpack_from("<II", data, 0x18)
    end = 0x800 + text_size
    stem = exe.name.lower().replace(".", "_")
    yaml = splat_common(exe.name, exe, stem)
    yaml += f"""  gp_value: 0x0
segments:
  - name: header
    type: header
    start: 0x0
  - name: main
    type: code
    start: 0x800
    vram: 0x{dest:08X}
    subsegments:
      - [0x800, asm, main]
  - [0x{end:X}]
"""
    path = CONFIG / f"{stem}.yaml"
    path.write_text(yaml)
    return path


def write_overlay(ov, ram_id: str | None) -> Path:
    stem = ov.path.stem.lower()
    extra = f"    exclusive_ram_id: {ram_id}\n" if ram_id else ""
    yaml = splat_common(ov.name, ov.path, stem)
    yaml += f"""segments:
  - name: {stem}
    type: code
    start: 0x0
    vram: 0x{ov.load:08X}
{extra}    subsegments:
      - [0x0, asm, {stem}]
  - [0x{ov.path.stat().st_size:X}]
"""
    path = CONFIG / f"{stem}.yaml"
    path.write_text(yaml)
    return path


def main() -> None:
    CONFIG.mkdir(exist_ok=True)
    exe = boot_exe()
    written = [write_exe(exe)]
    overlays = parse(GAME / "OVERLAY.DAT", GAME)
    loads: dict[int, list] = {}
    for ov in overlays:
        loads.setdefault(ov.load, []).append(ov)
    for load, group in loads.items():
        ram_id = f"vram_{load:08x}" if len(group) > 1 else None
        for ov in group:
            written.append(write_overlay(ov, ram_id))
    for path in written:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
