include config/compiler.mk

CONFIGS := $(wildcard config/*.yaml)
BUILD   := build

.PHONY: split objects objdiff-config

split:
	python3 tools/gen_splat.py
	splat split $(CONFIGS)

# Assemble splat disasm into expected objects for objdiff.
objects:
	python3 tools/make_objects.py

objdiff-config: objects
	python3 tools/make_objdiff.py

# Compile one C file to an object (used once src/ exists).
$(BUILD)/src/%.o: src/%.c
	@mkdir -p $(dir $@)
	$(CPP) -P $(CFLAGS) $< | $(CC1) -quiet $(CFLAGS) -o $(@:.o=.s)
	$(MASPSX) --aspsx-version=$(ASPSX_VER) --run-assembler --gnu-as-path=$(AS) \
		$(ASFLAGS) -o $@ $(@:.o=.s)
