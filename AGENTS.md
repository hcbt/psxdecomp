# PS1 matching decompilation

## devenv

All dependencies, services, tests, git hooks, and project tools come from devenv. Run every command as `devenv shell -- <cmd>`. Start services with `devenv up`. Run the project's tests the way devenv defines them (`devenv test` or the test task in `devenv.nix`).

Do not use host Python, Node, bun, or other host toolchains. Do not add a `.envrc`. Trust the project with `devenv allow`. After changing `devenv.nix` or `devenv.yaml`, confirm with a side effect, not a bare `devenv shell`.

`devenv shell -- ghidra-open` imports the disc EXE from `game/` if needed (SYSTEM.CNF `BOOT=`, else the first `PS-X EXE`), opens it in Ghidra, and starts the Ghidra MCP at `http://127.0.0.1:8080/mcp`.

`devenv shell -- splat-split` writes splat yamls from the EXE header + `OVERLAY.DAT` (into gitignored `config/`) and splits into `asm/`. `devenv shell -- ghidra-import-overlays` imports each overlay BIN at its load address. `devenv shell -- objects` then `objdiff-config` assemble expected objects and write `objdiff.json`. `devenv shell -- compile --src <dir>` runs old cc1 + maspsx on matching C. `devenv shell -- report --src <dir> --output <report.json>` writes the objdiff progress report (matched-code percent; fully-linked percent is `complete_code`). Put `report.json` in the decomp repo, not this toolkit. `devenv shell -- link` sha1s splat-assembled objects against the originals. Flags are in `tools/compiler.py`. Matching C (`src/`) and handwritten expected asm (`expected/`) are gitignored work products. Psy-Q is gitignored `tools/psyq/`. Matching a function needs Ghidra MCP (`inspect` decompile + listing) plus objdiff against original encodings.

Python is devenv `languages.python` with uv. Host C/C++ is devenv `languages.c` / `languages.cplusplus` (clang). Matching code still uses `cc1-*-psx`, not host clang. splat comes from the uv venv. Native matching tools (maspsx, old gcc, mipsel binutils, objdiff-cli, ninja) are devenv packages. Do not use host Python, cc, or as.

## APM

Agent skills and other agent primitives are declared in `apm.yml` and installed with `devenv shell -- apm install` (or `apm-cli` if that is the binary). Commit `apm.yml` (and `apm.lock.yaml` when APM writes one). Do not copy skills into the tree by hand.

The Ghidra MCP is declared under `dependencies.mcp` and deploys to `.vscode/mcp.json`. Grok reads the same server from `.grok/config.toml`. It talks to Ghidra's embedded MCP at `http://127.0.0.1:8080/mcp` after `devenv shell -- ghidra-open` is running with a program open.

## Git

Default branch is `master`. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## Context7

When the Context7 MCP is available in the session, use it for library, framework, SDK, API, CLI, and cloud-service documentation, including API syntax, configuration, setup, and version-specific behavior. Training-data knowledge of those libraries is stale. If Context7 is not available, continue without it; do not fail the task for that reason.
