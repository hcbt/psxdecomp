{ pkgs, lib, ... }:

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

  maspsxSrc = pkgs.fetchFromGitHub {
    owner = "mkst";
    repo = "maspsx";
    rev = "746b895f02929ecd148af7b1f4ff05b69f973878";
    hash = "sha256-B6p/V7zha3hurGjcOfAmbCcmUECj+uB6+O8rMmOEmUY=";
  };

  maspsx = pkgs.writeShellApplication {
    name = "maspsx";
    runtimeInputs = [ pkgs.python3 ];
    text = ''
      # Agent stdio is a pipe that never EOFs; maspsx readlines() stdin when
      # not a tty. Close it so a file argument is used instead of hanging.
      exec python3 ${maspsxSrc}/maspsx.py "$@" </dev/null
    '';
  };

  mkOldGcc =
    {
      version,
      url,
      hash,
    }:
    pkgs.stdenvNoCC.mkDerivation {
      pname = "gcc-${version}-psx";
      inherit version;
      src = pkgs.fetchurl { inherit url hash; };
      sourceRoot = ".";
      installPhase = ''
        runHook preInstall
        mkdir -p "$out/lib/gcc-${version}-psx" "$out/bin"
        cc1=$(find . -type f -name cc1 | head -n1)
        if [ -z "$cc1" ]; then
          echo "no cc1 in gcc-${version}-psx tarball" >&2
          find . -type f >&2
          exit 1
        fi
        cp -a "$(dirname "$cc1")/." "$out/lib/gcc-${version}-psx/"
        chmod +x "$out/lib/gcc-${version}-psx"/* || true
        for b in cc1 cpp gcc cc1plus g++; do
          if [ -e "$out/lib/gcc-${version}-psx/$b" ]; then
            # These tools read stdin when they have no input file. Agent
            # pipes never EOF, so a bad argv (e.g. -Ptest.c) hung for
            # minutes. Fail instead.
            cat > "$out/bin/$b-${version}-psx" <<EOF
#! /bin/sh
exec "$out/lib/gcc-${version}-psx/$b" "\$@" </dev/null
EOF
            chmod +x "$out/bin/$b-${version}-psx"
          fi
        done
        runHook postInstall
      '';
      meta = {
        description = "decompals GCC ${version} targeting mips-sony-psx";
        homepage = "https://github.com/decompals/old-gcc";
      };
    };

  oldGccSpecs =
    let
      darwin = pkgs.stdenv.hostPlatform.isDarwin;
      base = "https://github.com/decompals/old-gcc/releases/download/0.17";
    in
    [
      {
        version = "2.7.2";
        url =
          if darwin then "${base}/gcc-2.7.2-psx-macos.tar.gz" else "${base}/gcc-2.7.2-psx.tar.gz";
        hash =
          if darwin then
            "sha256-QoCJRmHJeSvBn1yXDCg9NTgZN/tE5HmpHQwETJX80gg="
          else
            "sha256-UApFmzSF6IWo0wLKwjwqRjLzkA4DoJFT9hkGmf1yNXE=";
      }
      {
        version = "2.8.1";
        url =
          if darwin then "${base}/gcc-2.8.1-psx-macos.tar.gz" else "${base}/gcc-2.8.1-psx.tar.gz";
        hash =
          if darwin then
            "sha256-urDG6h85RXPVqrvdezfjas7rg8UiFB2Uaoep9YwZnqA="
          else
            "sha256-9vbog5QtTTKJ0EgjbGcuce1BDlRqquj/ZVlS8VZ+G+A=";
      }
    ]
    ++ lib.optionals pkgs.stdenv.hostPlatform.isLinux [
      # No native macOS build of 2.8.0-psx in old-gcc 0.17.
      {
        version = "2.8.0";
        url = "${base}/gcc-2.8.0-psx.tar.gz";
        hash = "sha256-GjyVb+iupevbJRdJ2V3iyE8CNTBYTXvWY3RLXsJAULc=";
      }
    ];

  oldGccs = map mkOldGcc oldGccSpecs;

  objdiffCli =
    let
      system = pkgs.stdenv.hostPlatform.system;
      assets = {
        aarch64-darwin = {
          name = "objdiff-cli-macos-arm64";
          hash = "sha256-mPgnXCeQDE/iJI/OOvN2F2WL5JZI+n27WzdjcfBG39s=";
        };
        x86_64-darwin = {
          name = "objdiff-cli-macos-x86_64";
          hash = "sha256-E+JTXCUrjsttuna1qu8LwDxuNkYMc5/lrDWvFtiYUB4=";
        };
        x86_64-linux = {
          name = "objdiff-cli-linux-x86_64";
          hash = "sha256-yCkCgeghFLzBoG/3MGERDTkCoXeCLnUDN94lNxiONY8=";
        };
        aarch64-linux = {
          name = "objdiff-cli-linux-aarch64";
          hash = "sha256-qE3AXeZeuYHJfKhYkLvyz44d74pM4GIUTsxNDWhqmTo=";
        };
      };
      asset =
        assets.${system} or (throw "objdiff-cli: no upstream binary for ${system}");
    in
    pkgs.stdenvNoCC.mkDerivation {
      pname = "objdiff-cli";
      version = "3.8.1";
      src = pkgs.fetchurl {
        url = "https://github.com/encounter/objdiff/releases/download/v3.8.1/${asset.name}";
        inherit (asset) hash;
      };
      dontUnpack = true;
      nativeBuildInputs = lib.optionals pkgs.stdenv.hostPlatform.isLinux [
        pkgs.autoPatchelfHook
      ];
      installPhase = ''
        runHook preInstall
        mkdir -p $out/bin
        install -m755 $src $out/bin/objdiff-cli
        runHook postInstall
      '';
      meta = {
        description = "Object-file differ for matching decompilation";
        homepage = "https://github.com/encounter/objdiff";
      };
    };

  # Cross GNU as/ld targeting mipsel, no libc. pkgsCross.mipsel-linux-gnu
  # pulls glibc and fails to eval on Darwin.
  mipsBinutils = pkgs.stdenv.mkDerivation {
    pname = "mipsel-linux-gnu-binutils";
    inherit (pkgs.binutils-unwrapped) version src;
    nativeBuildInputs = [
      pkgs.bison
      pkgs.flex
      pkgs.texinfo
    ];
    configureFlags = [
      "--target=mipsel-linux-gnu"
      "--program-prefix=mipsel-linux-gnu-"
      "--disable-nls"
      "--disable-werror"
      "--disable-gprofng"
      "--enable-deterministic-archives"
    ];
    enableParallelBuilding = true;
    doCheck = false;
  };

  # Import the disc EXE if needed, then open Ghidra. GhidraMCP listens on
  # http://127.0.0.1:8080/mcp once the project window is up.
  launch = ''
    set -euo pipefail
    root="''${DEVENV_ROOT:-$(pwd)}"
    game_dir="$root/game"
    project_dir="$root/ghidra-project"

    mkdir -p "$project_dir"

    if [ "$(uname -s)" = Darwin ]; then
      pref="$HOME/Library/ghidra/${pkgs.ghidra.distroPrefix}"
    else
      pref="$HOME/.config/ghidra/${pkgs.ghidra.distroPrefix}"
    fi
    mkdir -p "$pref"
    if ! grep -q '^USER_AGREEMENT=ACCEPT' "$pref/preferences" 2>/dev/null; then
      {
        echo 'USER_AGREEMENT=ACCEPT'
        echo 'GhidraShowWhatsNew=false'
        echo 'SHOW_TIPS=false'
      } >> "$pref/preferences"
    fi

    gpr=""
    for candidate in "$project_dir"/*.gpr; do
      if [ -f "$candidate" ]; then
        gpr="$candidate"
        break
      fi
    done

    if [ -z "$gpr" ]; then
      exe=""
      if [ -f "$game_dir/SYSTEM.CNF" ]; then
        boot=$(grep -E '^BOOT=' "$game_dir/SYSTEM.CNF" | head -1 \
          | sed 's/^[Bb][Oo][Oo][Tt]=//;s/\\/\//g;s/;.*//;s|.*/||' \
          | tr -d '\r')
        if [ -n "$boot" ] && [ -f "$game_dir/$boot" ]; then
          exe="$game_dir/$boot"
        fi
      fi
      if [ -z "$exe" ]; then
        for f in "$game_dir"/*; do
          [ -f "$f" ] || continue
          if [ "$(head -c 8 "$f")" = "PS-X EXE" ]; then
            exe="$f"
            break
          fi
        done
      fi
      if [ -z "$exe" ]; then
        echo "no PS-X EXE in $game_dir (SYSTEM.CNF BOOT= or a file starting PS-X EXE)" >&2
        exit 1
      fi
      project_name=$(basename "$exe")
      gpr="$project_dir/$project_name.gpr"
      echo "importing $exe into $project_name..."
      ghidra-analyzeHeadless "$project_dir" "$project_name" -import "$exe"
    fi

    echo "Ghidra MCP: http://127.0.0.1:8080/mcp"
    # 12.1.2 only accepts a .gpr path (gpr:/program is a later Ghidra).
    exec ghidra "$gpr"
  '';
in
{
  packages = [
    pkgs.git
    pkgs.apm-cli
    pkgs.ninja
    ghidra
    maspsx
    objdiffCli
    mipsBinutils
  ]
  ++ oldGccs;

  env.GHIDRA_INSTALL_DIR = "${ghidra}/lib/ghidra";

  languages.python = {
    enable = true;
    venv.enable = true;
    uv.enable = true;
    uv.sync.enable = true;
    uv.sync.arguments = [ "--frozen" ];
  };

  languages.c.enable = true;
  languages.cplusplus.enable = true;

  scripts.ghidra-open.exec = launch;
  scripts.ghidra-mcp.exec = ''PYTHONPATH=${./tools}''${PYTHONPATH:+:$PYTHONPATH} python3 ${./tools}/ghidra_mcp.py "$@"'';
  scripts.splat-split.exec = ''PYTHONPATH=${./tools}''${PYTHONPATH:+:$PYTHONPATH} python3 ${./tools}/split.py "$@"'';
  scripts.ghidra-import-overlays.exec = ''PYTHONPATH=${./tools}''${PYTHONPATH:+:$PYTHONPATH} python3 ${./tools}/ghidra_import_overlays.py "$@"'';
  scripts.objects.exec = ''PYTHONPATH=${./tools}''${PYTHONPATH:+:$PYTHONPATH} python3 ${./tools}/make_objects.py "$@"'';
  scripts.objdiff-config.exec = ''PYTHONPATH=${./tools}''${PYTHONPATH:+:$PYTHONPATH} python3 ${./tools}/make_objdiff.py "$@"'';
  scripts.compile.exec = ''PYTHONPATH=${./tools}''${PYTHONPATH:+:$PYTHONPATH} python3 ${./tools}/compile.py "$@"'';
  scripts.report.exec = ''PYTHONPATH=${./tools}''${PYTHONPATH:+:$PYTHONPATH} python3 ${./tools}/report.py "$@"'';
  scripts.link.exec = ''PYTHONPATH=${./tools}''${PYTHONPATH:+:$PYTHONPATH} python3 ${./tools}/link.py "$@"'';

  enterTest = ''
    command -v ghidra
    command -v ghidra-analyzeHeadless
    command -v apm || command -v apm-cli
    command -v ghidra-open
    command -v ghidra-mcp
    command -v splat-split
    command -v ghidra-import-overlays
    command -v compile
    command -v report
    command -v link
    find "$GHIDRA_INSTALL_DIR/Ghidra/Extensions" -name extension.properties -print \
      | grep -q ghidra_psx_ldr
    find "$GHIDRA_INSTALL_DIR/Ghidra/Extensions" -name extension.properties -print \
      | grep -q GhidraMCP
    sla="$GHIDRA_INSTALL_DIR/Ghidra/Extensions/ghidra_psx_ldr/data/languages/mips32le.sla"
    test -f "$sla"
    test "$(head -c 3 "$sla")" = sla

    command -v clang
    command -v clang++
    for tool in python3 uv splat maspsx ninja objdiff-cli mipsel-linux-gnu-as mipsel-linux-gnu-ld cc1-2.8.1-psx cc1-2.7.2-psx clang clang++ mcp-proxy; do
      path="$(command -v "$tool")"
      case "$path" in
        /nix/store/*|*/.devenv/*|"$DEVENV_STATE"/venv/bin/*) echo "  ok $tool -> $path" ;;
        *) echo "  FAIL: $tool resolves to $path" >&2; exit 1 ;;
      esac
    done

    splat --help >/dev/null
    maspsx --help >/dev/null
    objdiff-cli --help >/dev/null
    mipsel-linux-gnu-as --version >/dev/null
    mipsel-linux-gnu-ld --version >/dev/null
    cc1_out="$(cc1-2.8.1-psx -version </dev/null 2>&1 || true)"
    echo "$cc1_out" | grep -q "GNU C version 2.8.1"
    python3 ${./tools}/test_make_objdiff.py
    python3 ${./tools}/test_ghidra_mcp.py
    python3 ${./tools}/test_compiler_stdin.py
  '';
}
