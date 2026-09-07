# Preserve structural artifact identity

Expected objects, reconstructed objects, comparison units, reports, and logs identify an artifact by binary, source-relative path, and symbol. Symbol names alone are not unique across game binaries and overlays, so flattening artifacts by symbol can silently compare the wrong files.
