# PS1 matching decompilation

## devenv

All dependencies, services, tests, git hooks, and project tools come from devenv. Run every command as `devenv shell -- <cmd>`. Start services with `devenv up`. Run the project's tests the way devenv defines them (`devenv test` or the test task in `devenv.nix`).

Do not use host Python, Node, bun, or other host toolchains. Do not add a `.envrc`. Trust the project with `devenv allow`. After changing `devenv.nix` or `devenv.yaml`, confirm with a side effect, not a bare `devenv shell`.

`devenv shell -- ghidra-open` imports the disc EXE from `game/` if needed (SYSTEM.CNF `BOOT=`, else the first `PS-X EXE`) and opens it in Ghidra. `devenv shell -- ghidra-mcp` is the stdio MCP server: it starts `ghidra-open` if `127.0.0.1:8080` is down, waits until `/mcp` answers, then proxies with mcp-proxy. If Ghidra is closed later, the same process starts `ghidra-open` again. MCP clients spawn `devenv shell -- ghidra-mcp` so handshake waits for the GUI instead of failing.

This devenv is meant to be imported by a game decomp. Data paths are `DEVENV_ROOT` (the importing project): disc dump in `game/` (gitignored), matching C in `src/`, splat `asm/` committed so CI can match without the dump. Psy-Q 4.7 headers ship in `tools/psyq/include`. A consumer may still put extra SDK files in its own `tools/psyq/`.

Consumers declare binaries, SHA-1 hashes, sizes, and compiler flags in `psxdecomp.toml`; their `meson.build` turns `psxdecomp plan` into explicit per-function, data, link, and verification targets. Run `devenv shell -- meson setup _build` once. The default `devenv shell -- meson compile -C _build` links and verifies every binary. `devenv shell -- meson compile -C _build progress` separately writes `_build/report.json` and `_build/objdiff.json`. After adding or removing a matching C file, run `devenv shell -- meson setup --reconfigure _build` so Meson refreshes source discovery. Invoke Meson through devenv; Ninja is the backend, not the public command interface.

`devenv shell -- psxdecomp regenerate` requires the private disc dump and transactionally replaces generated `asm/`, Splat TUs, configs, headers, and linker scripts while preserving matching per-function C. Commit those generated inputs so normal builds and CI need no disc. Ghidra commands remain independent of this build path. Matching uses Ghidra MCP (`inspect` decompile + listing), an explicit Meson function target during iteration, then the default whole-binary verification gate.

Python is devenv `languages.python` with uv. Host C/C++ is devenv `languages.c` / `languages.cplusplus` (clang). Matching code still uses `cc1-*-psx`, not host clang. splat comes from the uv venv. Native matching tools (maspsx, old gcc, mipsel binutils, objdiff-cli, ninja) are devenv packages. Do not use host Python, cc, or as.

## Git

Default branch is `master`. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## Context7

When the Context7 MCP is available in the session, use it for library, framework, SDK, API, CLI, and cloud-service documentation, including API syntax, configuration, setup, and version-specific behavior. Training-data knowledge of those libraries is stale. If Context7 is not available, continue without it; do not fail the task for that reason.
