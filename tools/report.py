#!/usr/bin/env python3
"""Generate an objdiff progress report (matched code + fully linked)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compiler import OBJCOPY, project_root
from splat_functions import extract_and_assemble, normalize_symbol, parse_all
import compile as compile_mod
import make_objdiff
import make_objects

ROOT = project_root()
SRC_DEFAULT = ROOT / "src"
SRC_FUNCS = ROOT / "build" / "src" / "funcs"
REPORT = ROOT / "report.json"


def compile_src(src_root: Path) -> list[Path]:
    files = sorted(src_root.rglob("*.c")) if src_root.is_dir() else []
    out = []
    for src in files:
        out.append(compile_mod.compile_c(src, src_root=src_root))
    return out


def map_compiled(objs: list[Path], funcs) -> int:
    by_key = {fn.key: fn.name for fn in funcs}
    SRC_FUNCS.mkdir(parents=True, exist_ok=True)
    n = 0
    for obj in objs:
        key = normalize_symbol(obj.stem)
        splat_name = by_key.get(key)
        if splat_name is None:
            print(f"warning: no splat function for {obj.name} ({key})", file=sys.stderr)
            continue
        dest = SRC_FUNCS / f"{splat_name}.o"
        nm = subprocess.run(
            ["mipsel-linux-gnu-nm", str(obj)],
            check=True,
            capture_output=True,
            text=True,
        )
        src_sym = None
        for line in nm.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] in {"T", "t"}:
                name = parts[2]
                if normalize_symbol(name) == key:
                    src_sym = name
                    break
        cmd = [OBJCOPY, str(obj), str(dest)]
        if src_sym and src_sym != splat_name:
            cmd = [OBJCOPY, f"--redefine-sym={src_sym}={splat_name}", str(obj), str(dest)]
        subprocess.run(cmd, check=True)
        n += 1
    return n


def generate_report(dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "objdiff-cli",
            "report",
            "generate",
            "-p",
            str(ROOT),
            "-o",
            str(dest),
            "-f",
            "json",
            "-c",
            "function_reloc_diffs=none",
        ],
        check=True,
    )
    text = dest.read_text()
    if "/Users/" in text or "/home/" in text:
        dest.unlink()
        raise SystemExit(f"refusing to write {dest}: report contains a local path")
    return json.loads(text)


def measures(report: dict) -> dict:
    m = report.get("measures") or {}
    if not m and "units" in report:
        # Sum from units if the CLI nests measures.
        total_code = matched_code = complete_code = 0
        total_fn = matched_fn = 0
        for unit in report.get("units", []):
            um = unit.get("measures") or {}
            total_code += int(um.get("total_code") or 0)
            matched_code += int(um.get("matched_code") or 0)
            complete_code += int(um.get("complete_code") or 0)
            total_fn += int(um.get("total_functions") or 0)
            matched_fn += int(um.get("matched_functions") or 0)
        m = {
            "total_code": total_code,
            "matched_code": matched_code,
            "complete_code": complete_code,
            "total_functions": total_fn,
            "matched_functions": matched_fn,
        }
    return m


def fmt_pct(num: int, den: int) -> str:
    if den == 0:
        return "n/a"
    return f"{100.0 * num / den:.4f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src",
        type=Path,
        default=SRC_DEFAULT,
        help="root of matching C (gitignored src/ by default)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=REPORT,
        help="objdiff report.json (put this in the decomp repo)",
    )
    parser.add_argument(
        "--skip-link",
        action="store_true",
        help="do not sha1-link splat objects against originals",
    )
    args = parser.parse_args()
    src_root = args.src.resolve()
    dest = args.output.expanduser().resolve()

    make_objects.main()
    funcs = parse_all()
    print(f"splat functions: {len(funcs)}")
    extract_and_assemble(funcs)
    compiled = compile_src(src_root) if src_root.is_dir() else []
    mapped = map_compiled(compiled, funcs)
    print(f"compiled {len(compiled)} C files, mapped {mapped} to splat names")
    make_objdiff.main()
    report = generate_report(dest)
    m = measures(report)
    total = int(m.get("total_code") or 0)
    matched = int(m.get("matched_code") or 0)
    complete = int(m.get("complete_code") or 0)
    print(f"matched code:  {matched} / {total} ({fmt_pct(matched, total)})")
    print(
        f"fully linked:  {complete} / {total} ({fmt_pct(complete, total)})"
        "  (C rebuild that sha1-matches the original; splat-asm roundtrip is separate)"
    )
    print(
        "functions:     "
        f"{int(m.get('matched_functions') or 0)} / {int(m.get('total_functions') or 0)}"
    )
    try:
        print(f"wrote {dest.relative_to(ROOT)}")
    except ValueError:
        print(f"wrote {dest}")

    if not args.skip_link:
        import link as link_mod

        print("link sha1 (splat objects, not C):")
        link_mod.main()


if __name__ == "__main__":
    main()
