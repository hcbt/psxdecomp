# Use one native toolkit CLI

Repository-owned Python for building, regeneration, reporting, and linking will be replaced by one typed Rust `psxdecomp` CLI with focused subcommands. A single native interface keeps binary parsing and structured transformations out of the build-language layer and consolidates filesystem ownership. External Python tools such as Splat remain dependencies, and the existing Ghidra Python integrations are explicitly outside this migration.
