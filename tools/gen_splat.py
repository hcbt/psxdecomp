#!/usr/bin/env python3
"""Write splat yamls for the boot EXE and every overlay that exists on disc.

The boot EXE (and each overlay when a .text range is found) is split into
.rodata / c / .data siblings of one TU so splat emits INCLUDE_ASM stubs.
.bss is only emitted when the PS-X EXE header's b_size is non-zero; trailing
zeros in the file stay .data so a link sha1 still matches the dump.
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compiler import project_root  # noqa: E402
from overlay_table import parse  # noqa: E402

ROOT = project_root()

GAME = ROOT / "game"
CONFIG = ROOT / "config"

ADDIU_SP = 0x27BD0000
JR_RA = 0x03E00008
# PSYQ TUs are small; a 16KiB gap between stack-frame prologues is a new region.
PROLOGUE_GAP = 0x4000
# jr $ra after the last prologue still belongs to .text (leaf epilogues, stubs).
EPILOGUE_WINDOW = 0x8000


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


def find_text_range(payload: bytes) -> tuple[int, int] | None:
    """Return payload offsets of .text, or None if no PSYQ-style .text is found.

    PSYQ functions usually start with `addiu $sp, $sp, -N`. Take the longest
    cluster of those prologues, walk back over `jr $ra` stubs, and end after
    the last `jr $ra` in a window past the last prologue.
    """
    if len(payload) < 16:
        return None
    nwords = len(payload) // 4
    prologues = [
        i * 4
        for i in range(nwords)
        if (struct.unpack_from("<I", payload, i * 4)[0] & 0xFFFF0000) == ADDIU_SP
        and struct.unpack_from("<I", payload, i * 4)[0] & 0x8000
    ]
    if len(prologues) < 2:
        return None
    best_s = best_e = run_s = prev = prologues[0]
    for p in prologues[1:]:
        if p - prev <= PROLOGUE_GAP:
            prev = p
            if prev - run_s > best_e - best_s:
                best_s, best_e = run_s, prev
        else:
            run_s = prev = p
    text_end = best_e + 4
    limit = min(len(payload), best_e + EPILOGUE_WINDOW)
    for off in range(best_e, limit - 3, 4):
        if struct.unpack_from("<I", payload, off)[0] == JR_RA:
            text_end = off + 8
    text_start = best_s
    while text_start >= 8:
        if struct.unpack_from("<I", payload, text_start - 8)[0] == JR_RA:
            text_start -= 8
        else:
            break
    text_start &= ~3
    text_end = min(len(payload), (text_end + 3) & ~3)
    if text_end <= text_start:
        return None
    return text_start, text_end


def format_subsegments(file_start: int, payload: bytes, tu: str) -> str:
    found = find_text_range(payload)
    if found is None:
        return f"      - [{_hex(file_start)}, c, {tu}]\n"
    text_off, text_end = found
    lines: list[str] = []
    if text_off > 0:
        lines.append(f"      - [{_hex(file_start)}, rodata, rodata]")
    lines.append(f"      - [{_hex(file_start + text_off)}, c, {tu}]")
    if text_end < len(payload):
        lines.append(f"      - [{_hex(file_start + text_end)}, data, data]")
    return "".join(line + "\n" for line in lines)


def _hex(n: int) -> str:
    return hex(n) if n else "0x0"


def splat_common(name: str, target: Path, basename: str, gp_value: int) -> str:
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
  include_asm_macro_style: maspsx_hack
  create_c_files: True
  migrate_rodata_to_functions: False
  ld_align_section_vram_end: False
  ld_align_segment_vram_end: False
  section_order: [".rodata", ".text", ".data", ".bss"]
  ld_bss_is_noload: False
  symbol_addrs_path:
    - config/symbol_addrs.txt
  reloc_addrs_path:
    - config/reloc_addrs.txt
  undefined_funcs_auto_path: config/undefined_funcs_auto.txt
  undefined_syms_auto_path: config/undefined_syms_auto.txt
  subalign: 4
  string_encoding: ASCII
  data_string_encoding: ASCII
  gp_value: {hex(gp_value)}
"""


def write_exe(exe: Path) -> Path:
    data = exe.read_bytes()
    gp0, dest, text_size, _d_addr, _d_size, b_addr, b_size = struct.unpack_from(
        "<IIIIIII", data, 0x14
    )
    end = 0x800 + text_size
    payload = data[0x800:end]
    stem = exe.name.lower().replace(".", "_")
    yaml = splat_common(exe.name, exe, stem, gp0)
    yaml += f"""segments:
  - name: header
    type: header
    start: 0x0
  - name: main
    type: code
    start: 0x800
    vram: 0x{dest:08X}
    align: 4
    subsegments:
{format_subsegments(0x800, payload, "main")}"""
    if b_size:
        bss_vram = b_addr if b_addr else dest + text_size
        yaml += f"""      - {{ start: {_hex(end)}, type: bss, vram: 0x{bss_vram:08X}, name: bss }}
"""
    yaml += f"  - [{_hex(end)}]\n"
    path = CONFIG / f"{stem}.yaml"
    path.write_text(yaml)
    return path


def write_overlay(ov, ram_id: str | None) -> Path:
    stem = ov.path.stem.lower()
    extra = f"    exclusive_ram_id: {ram_id}\n" if ram_id else ""
    data = ov.path.read_bytes()
    yaml = splat_common(ov.name, ov.path, stem, 0)
    yaml += f"""segments:
  - name: {stem}
    type: code
    start: 0x0
    vram: 0x{ov.load:08X}
    align: 4
{extra}    subsegments:
{format_subsegments(0, data, stem)}  - [{_hex(ov.path.stat().st_size)}]
"""
    path = CONFIG / f"{stem}.yaml"
    path.write_text(yaml)
    return path


def ensure_addr_files() -> None:
    CONFIG.mkdir(exist_ok=True)
    for name in ("symbol_addrs.txt", "reloc_addrs.txt"):
        path = CONFIG / name
        if not path.exists():
            path.write_text("")


def main() -> None:
    ensure_addr_files()
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
