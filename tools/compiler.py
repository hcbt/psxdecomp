"""Matching-compiler defaults. Unproven until a leaf is 100%."""

CC1 = "cc1-2.8.1-psx"
CPP = "cpp-2.8.1-psx"
ASPSX_VER = "2.79"
CFLAGS = ["-O2", "-G0"]
# Host `as` is Clang on macOS. Always the mipsel GNU assembler.
AS = "mipsel-linux-gnu-as"
# r4000 so splat `tge` is accepted (ASPSX emits it on R3000 too).
ASFLAGS = ["-EL", "-march=r4000", "-no-pad-sections"]
MASPSX = "maspsx"
