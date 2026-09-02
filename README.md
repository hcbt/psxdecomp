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

The importing project is `DEVENV_ROOT`. Put the disc dump in `game/`, matching C in `src/`, and `report.json` at the repo root. Psy-Q 4.7 headers are in `tools/psyq/include`.

```
devenv allow
devenv shell -- ghidra-open
devenv shell -- splat-split
devenv shell -- compile
devenv shell -- report
```
