{ pkgs, ... }:

let
  ghidraPsxLdr = pkgs.ghidra.buildGhidraExtension {
    pname = "ghidra_psx_ldr";
    version = "2026.07.08";

    src = pkgs.fetchFromGitHub {
      owner = "lab313ru";
      repo = "ghidra_psx_ldr";
      rev = "2026.07.08";
      hash = "sha256-/8S16vOfCj2bQcrO8rRWqAGVhdNHI6DhRNFTu9RP4PI=";
      fetchSubmodules = true;
    };

    nativeBuildInputs = [ pkgs.ant ];

    # Upstream ships an XML .sla. Ghidra 12 wants the compiled binary format.
    configurePhase = ''
      runHook preConfigure
      rm -f data/languages/*.sla
      pushd data
      ant -f build.xml -Dghidra.install.dir=${pkgs.ghidra}/lib/ghidra sleighCompile
      popd
      runHook postConfigure
    '';

    meta = {
      description = "Sony PlayStation PSX executables loader for Ghidra";
      homepage = "https://github.com/lab313ru/ghidra_psx_ldr";
    };
  };

  ghidra = pkgs.ghidra.withExtensions (_: [ ghidraPsxLdr ]);
in
{
  packages = [
    pkgs.git
    ghidra
  ];

  env.GHIDRA_INSTALL_DIR = "${ghidra}/lib/ghidra";

  enterTest = ''
    command -v ghidra
    command -v ghidra-analyzeHeadless
    find "$GHIDRA_INSTALL_DIR/Ghidra/Extensions" -name extension.properties -print \
      | grep -q ghidra_psx_ldr
    sla="$GHIDRA_INSTALL_DIR/Ghidra/Extensions/ghidra_psx_ldr/data/languages/mips32le.sla"
    test -f "$sla"
    test "$(head -c 3 "$sla")" = sla
  '';
}
