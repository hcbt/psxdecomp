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

The importing project is `DEVENV_ROOT`. Put the disc dump in `game/`, matching C in `src/`, Psy-Q headers/libs in `tools/psyq/`, and `report.json` at the repo root.

```
devenv allow
devenv shell -- ghidra-open
devenv shell -- splat-split
devenv shell -- compile
devenv shell -- report
```
