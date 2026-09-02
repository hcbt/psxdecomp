# buddies

## devenv

All dependencies, services, tests, git hooks, and project tools come from devenv. Run every command as `devenv shell -- <cmd>`. Start services with `devenv up`. Run the project's tests the way devenv defines them (`devenv test` or the test task in `devenv.nix`).

Do not use host Python, Node, bun, or other host toolchains. Do not add a `.envrc`. Trust the project with `devenv allow`. After changing `devenv.nix` or `devenv.yaml`, confirm with a side effect, not a bare `devenv shell`.

`devenv shell -- buddies` imports `game/SLUS_008.69` if needed, opens it in Ghidra, and starts the Ghidra MCP at `http://127.0.0.1:8080/mcp`.

## APM

Agent skills and other agent primitives are declared in `apm.yml` and installed with `devenv shell -- apm install` (or `apm-cli` if that is the binary). Commit `apm.yml` (and `apm.lock.yaml` when APM writes one). Do not copy skills into the tree by hand.

The Ghidra MCP is declared under `dependencies.mcp` and deploys to `.vscode/mcp.json`. Grok reads the same server from `.grok/config.toml`. It talks to Ghidra's embedded MCP at `http://127.0.0.1:8080/mcp` after `devenv shell -- ghidra` is running with a program open.

## Git

Default branch is `master`. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## Context7

When the Context7 MCP is available in the session, use it for library, framework, SDK, API, CLI, and cloud-service documentation, including API syntax, setup, and version-specific behavior. Training-data knowledge of those libraries is stale. If Context7 is not available, continue without it; do not fail the task for that reason.
