# Reuse compared objects for linking

The exact reconstructed function objects compared by objdiff are also inputs to the final linked binaries. Meson builds each object once and shares it across progress reporting and linking, so a function's reported match describes the code that binary verification actually consumes.
