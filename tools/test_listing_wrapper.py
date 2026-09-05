#!/usr/bin/env python3
"""Per-function matching C must be C; GNU asm is a listing wrapper."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compile import compile_c, is_splat_tu, listing_wrapper_reason


def _write(tmp: str, name: str, text: str) -> Path:
    path = Path(tmp) / name
    path.write_text(text)
    return path


def test_real_c_is_not_a_wrapper() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = _write(
            tmp,
            "fun_8001a968.c",
            "void fun_8001a968(void) {\n    CdInit();\n}\n",
        )
        assert listing_wrapper_reason(src) is None, listing_wrapper_reason(src)
    print("ok real_c_is_not_a_wrapper")


def test_splat_tu_with_include_asm_is_not_a_wrapper() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = _write(
            tmp,
            "main.c",
            '#include "common.h"\nINCLUDE_ASM("asm/slus_008_69/nonmatchings/main", func_80019CF8);\n',
        )
        assert is_splat_tu(src)
        assert listing_wrapper_reason(src) is None, listing_wrapper_reason(src)
    print("ok splat_tu_with_include_asm_is_not_a_wrapper")


def test_listing_block_is_a_wrapper() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = _write(
            tmp,
            "func_80025620.c",
            '__asm__(\n'
            '    "\\t.set\\tnoreorder\\n"\n'
            '    "\\t.globl func_80025620\\n"\n'
            '    "func_80025620:\\n"\n'
            '    "jr $ra\\n"\n'
            '    "nop\\n"\n'
            '    "\\t.set\\treorder"\n'
            ');\n',
        )
        reason = listing_wrapper_reason(src)
        assert reason is not None
        assert "func_80025620.c" in reason
        assert "__asm__" in reason
    print("ok listing_block_is_a_wrapper")


def test_register_asm_is_a_wrapper() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = _write(
            tmp,
            "func_8001D8D8.c",
            "int func_8001D8D8(int a0) {\n"
            '    register int v0 __asm__("$2");\n'
            "    return v0;\n"
            "}\n",
        )
        assert listing_wrapper_reason(src) is not None
    print("ok register_asm_is_a_wrapper")


def test_asm_nop_is_a_wrapper() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = _write(
            tmp,
            "func_8001D834.c",
            "void func_8001D834(int a0) {\n"
            '    __asm__("nop");\n'
            "    *p = a0;\n"
            "}\n",
        )
        assert listing_wrapper_reason(src) is not None
    print("ok asm_nop_is_a_wrapper")


def test_include_asm_path_is_not_a_wrapper() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = _write(
            tmp,
            "func_8001a000.c",
            '#include "asm/labels.h"\nvoid func_8001a000(void) {}\n',
        )
        assert listing_wrapper_reason(src) is None, listing_wrapper_reason(src)
    print("ok include_asm_path_is_not_a_wrapper")


def test_asm_in_comment_is_not_a_wrapper() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = _write(
            tmp,
            "func_8001a000.c",
            "void func_8001a000(void) {\n"
            '    /* __asm__("nop"); */\n'
            "    // __asm__(\".set noreorder\")\n"
            "}\n",
        )
        assert listing_wrapper_reason(src) is None, listing_wrapper_reason(src)
    print("ok asm_in_comment_is_not_a_wrapper")


def test_compile_c_rejects_wrapper() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = _write(tmp, "func_80025620.c", '__asm__("nop");\n')
        try:
            compile_c(src)
        except SystemExit as exc:
            assert "__asm__" in str(exc)
            return
        raise AssertionError("compile_c accepted a listing wrapper")


if __name__ == "__main__":
    test_real_c_is_not_a_wrapper()
    test_splat_tu_with_include_asm_is_not_a_wrapper()
    test_listing_block_is_a_wrapper()
    test_register_asm_is_a_wrapper()
    test_asm_nop_is_a_wrapper()
    test_include_asm_path_is_not_a_wrapper()
    test_asm_in_comment_is_not_a_wrapper()
    test_compile_c_rejects_wrapper()
    print("ok compile_c_rejects_wrapper")
