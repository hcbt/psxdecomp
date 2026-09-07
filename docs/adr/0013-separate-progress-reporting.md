# Separate progress reporting

The default Meson build compiles, links, and verifies every game binary, while an explicit `progress` target generates the objdiff/decomp.dev `report.json` from the same cached objects. CI runs both, but ordinary builds avoid paying the reporting cost when no publishable progress artifact is needed.
