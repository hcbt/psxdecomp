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

  # Prebuilt themixednuts/GhidraMCP. Native HTTP MCP at 127.0.0.1:8080/mcp.
  ghidraMcp = pkgs.stdenvNoCC.mkDerivation {
    pname = "GhidraMCP";
    version = "0.8.0";
    src = pkgs.fetchurl {
      url = "https://github.com/themixednuts/GhidraMCP/releases/download/v0.8.0/GhidraMCP-0.8.0.zip";
      hash = "sha256-DQ7tPNTxasV0tVijK11uE6s/ek42cpqtHolk6kgME9s=";
    };
    nativeBuildInputs = [ pkgs.unzip ];
    dontUnpack = true;
    dontBuild = true;
    installPhase = ''
      runHook preInstall
      mkdir -p $out/lib/ghidra/Ghidra/Extensions
      unzip -d $out/lib/ghidra/Ghidra/Extensions $src
      substituteInPlace $out/lib/ghidra/Ghidra/Extensions/GhidraMCP/extension.properties \
        --replace-fail 'version=12.1' 'version=${pkgs.ghidra.version}'
      echo >> $out/lib/ghidra/Ghidra/Extensions/GhidraMCP/extension.properties
      touch $out/lib/ghidra/Ghidra/Extensions/GhidraMCP/.dbDirLock
      runHook postInstall
    '';
    meta = {
      description = "Ghidra extension that embeds an MCP HTTP server";
      homepage = "https://github.com/themixednuts/GhidraMCP";
    };
  };

  ghidra = pkgs.ghidra.withExtensions (_: [
    ghidraPsxLdr
    ghidraMcp
  ]);
in
{
  packages = [
    pkgs.git
    pkgs.apm-cli
    ghidra
  ];

  env.GHIDRA_INSTALL_DIR = "${ghidra}/lib/ghidra";

  enterTest = ''
    command -v ghidra
    command -v ghidra-analyzeHeadless
    command -v apm || command -v apm-cli
    find "$GHIDRA_INSTALL_DIR/Ghidra/Extensions" -name extension.properties -print \
      | grep -q ghidra_psx_ldr
    find "$GHIDRA_INSTALL_DIR/Ghidra/Extensions" -name extension.properties -print \
      | grep -q GhidraMCP
    sla="$GHIDRA_INSTALL_DIR/Ghidra/Extensions/ghidra_psx_ldr/data/languages/mips32le.sla"
    test -f "$sla"
    test "$(head -c 3 "$sla")" = sla
  '';
}
