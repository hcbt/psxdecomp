# PS1 matching decompilation

## devenv

All dependencies, services, tests, git hooks, and project tools come from devenv. Run every command as `devenv shell -- <cmd>`. Start services with `devenv up`. Run the project's tests the way devenv defines them (`devenv test` or the test task in `devenv.nix`).

Do not use host Python, Node, bun, or other host toolchains. Do not add a `.envrc`. Trust the project with `devenv allow`. After changing `devenv.nix` or `devenv.yaml`, confirm with a side effect, not a bare `devenv shell`.

`devenv shell -- ghidra-open` imports the disc EXE from `game/` if needed (SYSTEM.CNF `BOOT=`, else the first `PS-X EXE`), opens it in Ghidra, and starts the Ghidra MCP at `http://127.0.0.1:8080/mcp`.

This devenv is meant to be imported by a game decomp. Data paths are `DEVENV_ROOT` (the importing project): disc dump in `game/` (gitignored), matching C in `src/`, splat `asm/` committed so CI can match without the dump. Psy-Q 4.7 headers ship in `tools/psyq/include`. A consumer may still put extra SDK files in its own `tools/psyq/`.

`devenv shell -- splat-split` writes splat yamls from the EXE header + `OVERLAY.DAT` into `config/` and splits into `asm/`. Every binary (boot EXE and overlay BINs) uses `.rodata` / `c` / `.data` when `tools/gen_splat.py` finds a PSYQ `.text` range (`addiu $sp, $sp, -N` cluster). splat then writes `src/<tu>/<name>.c` with `INCLUDE_ASM` (not overwritten if the file exists) and `include/common.h` if missing. `split.py` rewrites INCLUDE_ASM folders to repo-relative paths, inserts any splat-omitted `.L` branch labels, and replaces a stub with `#include "<fn>.c"` when that per-function file exists. Curated `symbol_addrs.txt` / `reloc_addrs.txt` and splat's `undefined_*_auto.txt` live in `config/` too. `devenv shell -- ghidra-import-overlays` imports each overlay BIN at its load address. `devenv shell -- objects` then `objdiff-config` assemble expected objects and write gitignored `objdiff.json`. `devenv shell -- compile` runs old cc1 + maspsx on `src/**/*.c` with `-I include` (game headers) and Psy-Q headers. `devenv shell -- report` prints matched-code percent (`complete_code` is fully linked) and writes gitignored `report.json`; it compiles per-function .c only, not splat TUs. CI runs `compile` then `report --skip-link` and uploads `report.json` as `{version}_report` for decomp.dev. `devenv shell -- link` compiles C objects listed in the splat ld scripts (else splat asm) and sha1s against the originals. Flags are in `tools/compiler.py`. Matching a function needs Ghidra MCP (`inspect` decompile + listing) plus objdiff against original encodings.

Python is devenv `languages.python` with uv. Host C/C++ is devenv `languages.c` / `languages.cplusplus` (clang). Matching code still uses `cc1-*-psx`, not host clang. splat comes from the uv venv. Native matching tools (maspsx, old gcc, mipsel binutils, objdiff-cli, ninja) are devenv packages. Do not use host Python, cc, or as.

## APM

Agent skills and other agent primitives are declared in `apm.yml` and installed with `devenv shell -- apm install` (or `apm-cli` if that is the binary). Commit `apm.yml` (and `apm.lock.yaml` when APM writes one). Do not copy skills into the tree by hand.

The Ghidra MCP is declared under `dependencies.mcp` and deploys to `.vscode/mcp.json`. Grok reads the same server from `.grok/config.toml`. It talks to Ghidra's embedded MCP at `http://127.0.0.1:8080/mcp` after `devenv shell -- ghidra-open` is running with a program open.

## Git

Default branch is `master`. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## Context7

When the Context7 MCP is available in the session, use it for library, framework, SDK, API, CLI, and cloud-service documentation, including API syntax, configuration, setup, and version-specific behavior. Training-data knowledge of those libraries is stale. If Context7 is not available, continue without it; do not fail the task for that reason.
