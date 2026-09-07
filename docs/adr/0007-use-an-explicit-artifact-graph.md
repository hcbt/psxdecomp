# Use an explicit artifact graph

Meson tracks each source-to-object transformation, binary link, and hash check as an individual graph edge. The native toolkit supplies focused commands for those edges rather than hiding compilation and linking behind one aggregate command, preserving correct incremental rebuilding and parallelism.
