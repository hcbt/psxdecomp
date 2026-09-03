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

The importing project is `DEVENV_ROOT`. Put the disc dump in `game/` (gitignored). Matching C lives in `src/` (per-function files plus splat TUs with `INCLUDE_ASM`). Commit splat `asm/` so CI can run `compile` then `report --skip-link` without `game/`. splat yamls and address lists go in `config/`, with a stub `include/common.h`. Psy-Q 4.7 headers are in `tools/psyq/include`. `splat-split` cuts `.rodata` / `.text` (type `c`) / `.data` on the boot EXE and on overlay BINs when it can find PSYQ stack-frame prologues, writes `INCLUDE_ASM` stubs, fills in splat-omitted `.L` branch labels, and inlines any matching `src/<tu>/<fn>.c`. `link` compiles those TUs and sha1s against the originals.

`devenv shell -- report` prints matched-code percent and writes gitignored `report.json` plus `objdiff.json`. Do not commit either file. CI uploads `report.json` as a `{version}_report` artifact for decomp.dev.

```
devenv allow
devenv shell -- ghidra-open
devenv shell -- splat-split
devenv shell -- compile
devenv shell -- report
```
