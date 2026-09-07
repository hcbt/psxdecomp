# PS1 Matching Decompilation Toolkit

This context describes the shared language for reconstructing PlayStation 1 game binaries from matching source code.

## Language

**Toolkit**:
The reusable capabilities and conventions that multiple game projects consume to reconstruct and verify their binaries.
_Avoid_: Template, game build

**Game project**:
A repository containing the committed configuration, assembly, and reconstructed source for one game.
_Avoid_: Consumer, downstream

**Project manifest**:
The authoritative declaration of a game project's binaries, overlays, compiler settings, and expected hashes.
_Avoid_: Splat configuration, build script

**Regeneration**:
The explicit, destructive reconstruction of a game project's committed configuration and assembly from its private disc data.
_Avoid_: Build, split

**Build**:
The deterministic transformation of a game project's committed inputs into object files and reconstructed binaries.
_Avoid_: Regeneration, compile

**Verification**:
The comparison of reconstructed artifacts with original game artifacts to establish matching equivalence.
_Avoid_: Build, report

**Artifact identity**:
The combination of binary, source-relative path, and symbol that uniquely identifies a reconstructed or expected artifact.
_Avoid_: Symbol name, function name

**Object match**:
Agreement between an isolated reconstructed object and its corresponding expected object.
_Avoid_: Binary match, complete match

**Binary match**:
Agreement between an entire reconstructed game binary and its original artifact.
_Avoid_: Object match, function match
