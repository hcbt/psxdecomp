# psxdecomp

Reusable PlayStation 1 matching-decomp toolchain: Meson, Ninja, a native
`psxdecomp` CLI, Splat, old GCC, maspsx, GNU binutils, objdiff, and Ghidra.

Import it from a game decomp's `devenv.yaml`:

```yaml
inputs:
  psxdecomp:
    url: github:hcbt/psxdecomp
    flake: false
imports:
  - psxdecomp
```

The consumer owns `psxdecomp.toml` and `meson.build`. Commit its Splat assembly,
linker scripts, and generated undefined-symbol files so CI can reconstruct every
binary without the private disc dump. Meson describes the build graph, Ninja is
its backend, and `psxdecomp` performs the PS1-specific leaf operations.

The default build compiles changed candidate functions, compares them with
objdiff, links every executable and overlay, and verifies each result against the
SHA-1 recorded in `psxdecomp.toml`. Progress reporting is separate and writes
`_build/report.json` plus `_build/objdiff.json`.

```sh
devenv allow
devenv shell -- meson setup _build
devenv shell -- meson compile -C _build
devenv shell -- meson compile -C _build progress
devenv shell -- ghidra-open
```

Regeneration is an explicit, transactional operation that requires the private
disc in `game/`:

```sh
devenv shell -- psxdecomp regenerate
devenv shell -- meson setup --reconfigure _build
```

The Rust compiler is enabled only in this toolkit repository. Consumers receive
the packaged CLI and all toolchain binaries through their imported devenv.
