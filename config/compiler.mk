# Unproven until a leaf is 100%. Override on the make command line.
CC1       ?= cc1-2.8.1-psx
CPP       ?= cpp-2.8.1-psx
ASPSX_VER ?= 2.79
CFLAGS    ?= -O2 -G0
AS        ?= mipsel-linux-gnu-as
ASFLAGS   ?= -EL -march=r4000 -no-pad-sections
MASPSX    ?= maspsx
