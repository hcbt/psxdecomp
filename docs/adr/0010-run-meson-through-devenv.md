# Run Meson through devenv

Devenv provisions the packaged `psxdecomp` CLI, Meson, Ninja, objdiff, and the complete PS1 toolchain for game projects; all Meson setup, compilation, testing, and CI commands run through `devenv shell --`. The toolkit repository alone carries the Rust development toolchain, while game projects consume the native CLI as a Nix-built package and do not compile it during shell entry.
