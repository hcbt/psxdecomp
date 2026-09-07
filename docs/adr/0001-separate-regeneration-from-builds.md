# Separate regeneration from builds

Regeneration from private disc data is an explicit, destructive project-maintenance operation, while ordinary builds consume committed configuration, assembly, and source. Keeping these workflows separate makes builds deterministic and usable in disc-less CI without allowing routine builds to rewrite project inputs.
