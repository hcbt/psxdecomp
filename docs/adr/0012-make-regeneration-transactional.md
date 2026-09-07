# Make regeneration transactional

Regeneration writes and validates a complete replacement tree before changing committed configuration or assembly. Only a successful run replaces the existing artifacts, so disc parsing, Splat, or post-processing failures cannot leave a game project partially deleted or regenerated.
