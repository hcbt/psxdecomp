# Use a project manifest

Each game project keeps an authoritative `psxdecomp.toml` declaring its binaries, overlays, compiler settings, and expected hashes. Splat YAML files and the large assembly inventory remain committed regeneration artifacts for public, disc-less builds rather than serving as the toolkit's primary project configuration. Reconstructed sources identify themselves through the canonical `src/<binary>/<symbol>.c` path; after adding one, an explicit Meson reconfigure discovers it and writes a fully explicit build graph without duplicating every source in the manifest.
