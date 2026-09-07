# Require binary verification

A successful default build links every executable and overlay and verifies each result against its committed expected hash. Explicit per-function targets may stop after comparison to support fast matching work, but they do not constitute a successful complete build; CI enforces both progress reporting and binary verification without requiring private disc data because game projects commit the expected hashes.
