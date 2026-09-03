# psxdecomp

Generic PlayStation 1 matching-decomp environment: Ghidra, splat, maspsx, old gcc, objdiff.

Import it from a game decomp's `devenv.yaml`:

```yaml
inputs:
  psxdecomp:
    url: github:hcbt/psxdecomp
    flake: false
imports:
  - psxdecomp
```

The importing project is `DEVENV_ROOT`. Put the disc dump in `game/`, matching C in `src/` (per-function files plus splat TUs with `INCLUDE_ASM`), splat yamls and address lists in `config/`, a stub `include/common.h`, and `report.json` at the repo root. Psy-Q 4.7 headers are in `tools/psyq/include`. `splat-split` cuts `.rodata` / `.text` (type `c`) / `.data` on the boot EXE and on overlay BINs when it can find PSYQ stack-frame prologues, writes `INCLUDE_ASM` stubs, fills in splat-omitted `.L` branch labels, and inlines any matching `src/<tu>/<fn>.c`. `link` compiles those TUs and sha1s against the originals.

```
devenv allow
devenv shell -- ghidra-open
devenv shell -- splat-split
devenv shell -- compile
devenv shell -- report
```
