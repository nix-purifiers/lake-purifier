{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  buildLakePackage,
  lean4,
  gcc,
  nativeInspector,
  sdkVersion,
  gnutar,
  gzip,
  binutils,
  stdenv,
}@scope:
{
  src,
  lockFile ? src + "/lake-purifier.lock.json",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  buildTargets ? [ ],
  doCheck ? false,
  checkPhase ? "",
  installPhase ? null,
  nativeProducts ? { },
  sharedDependencies ? false,
}:
let
  selected = nativeProducts != { };
  relative =
    value:
    builtins.isString value
    && value != ""
    && !(lib.hasPrefix "/" value)
    && !(builtins.elem ".." (lib.splitString "/" value));
  symbol = value: builtins.isString value && builtins.match "[A-Za-z_][A-Za-z0-9_]*" value != null;
  validProduct =
    name: product:
    builtins.match "[A-Za-z_][A-Za-z0-9_.]*" name != null
    && builtins.elem name lock.data.project.libraries
    &&
      builtins.attrNames (builtins.removeAttrs product [ "target" ]) == [
        "exports"
        "header"
        "initializeSymbol"
        "library"
      ]
    && (
      !(product ? target)
      || (
        builtins.isString product.target && builtins.match "[A-Za-z_][A-Za-z0-9_.]*" product.target != null
      )
    )
    && relative product.library
    && relative product.header
    && symbol product.initializeSymbol
    && builtins.isList product.exports
    && product.exports != [ ]
    && builtins.all symbol product.exports
    &&
      builtins.length (lib.unique (product.exports ++ [ product.initializeSymbol ]))
      == builtins.length product.exports + 1;
  productsInspector = import ./native-products-inspector.nix { inherit runCommand lean4 gcc; };
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } { inherit src lockFile; }
  );
  deps =
    import ./environment.nix
      (builtins.removeAttrs scope [
        "gnutar"
        "gzip"
        "binutils"
        "stdenv"
      ])
      {
        inherit lock fetchers nativeBuildInputs;
        sharedLibraries = selected || sharedDependencies;
      };
  expected = writeText "lake-root.json" (builtins.toJSON lock.data.project);
  overrides = writeText "lake-overrides.json" (
    builtins.toJSON {
      schemaVersion = "1.2.0";
      packages = map (node: {
        type = "path";
        name = node.name;
        inherited = false;
        dir = toString deps.packages.${node.name};
      }) lock.data.nodes;
    }
  );
  builtProject = buildLakePackage (
    {
      pname = "purified-lake-${lock.data.project.name}";
      version = lock.data.project.version;
      src = lib.cleanSourceWith {
        inherit src;
        filter =
          path: type:
          !(builtins.elem (baseNameOf path) [
            ".git"
            ".lake"
            ".lake-purifier"
            "result"
            "__pycache__"
          ]);
      };
      leanPackageName = lock.data.project.name;
      leanDeps = map (name: deps.packages.${name}) lock.data.project.dependencies;
      buildTargets =
        buildTargets
        ++ map (name: nativeProducts.${name}.target or (name + ":shared")) (
          builtins.attrNames nativeProducts
        );
      inherit
        nativeBuildInputs
        doCheck
        checkPhase
        ;
      preConfigure = ''
        export LEAN_SYSROOT=${lean4}
        export LEAN_CC=${gcc}/bin/cc
        ${nativeInspector}/bin/lake-inspect "$PWD" > "$TMPDIR/native.json"
        ${python3}/bin/python3 ${../../lake_purifier/check-metadata.py} ${expected} "$TMPDIR/native.json"
        ${lib.optionalString selected ''
          ${python3}/bin/python3 ${./verify-native.py} capture "$src" "$TMPDIR/native-source.json"
        ''}
      '';
      postConfigure = "export LEAN_NUM_THREADS=2";
      postBuild = lib.optionalString selected ''
        ${productsInspector}/bin/lake-native-products "$PWD" > "$TMPDIR/native-products.json"
        ${python3}/bin/python3 ${./query-native.py} ${lean4}/bin/lake ${overrides} \
          ${writeText "lake-native-products.json" (builtins.toJSON nativeProducts)} "$TMPDIR/native-queries.json"
      '';
      postInstall = lib.optionalString selected ''
        mkdir -p "$out/include"
        if [ ! -e "$out/include/lean" ]; then
          ln -s ${lean4}/include/lean "$out/include/lean"
        else
          test "$(readlink -f "$out/include/lean")" = ${lean4}/include/lean
        fi
        ${python3}/bin/python3 ${./verify-native.py} verify "$PWD" "$out" \
          "$TMPDIR/native-products.json" "$TMPDIR/native-source.json" \
          ${writeText "lake-native-products.json" (builtins.toJSON nativeProducts)} \
          ${lean4} ${binutils}/bin/nm ${stdenv.cc.bintools.libc_bin}/bin/ldd "$TMPDIR/native-queries.json"
      '';
    }
    // lib.optionalAttrs selected {
      dontPatchELF = true;
      dontStrip = true;
    }
    // lib.optionalAttrs (installPhase != null) {
      installPhase = installPhase + "\nrunHook postInstall\n";
    }
  );
  projections = lib.optionalAttrs selected (
    purifier.nativeProjections {
      producer = builtProject;
      libraries = lib.mapAttrs (_: product: product.library) nativeProducts;
      includeDirectories = [
        "include"
      ]
      ++ map (name: "include/lake-native/${name}") (builtins.attrNames nativeProducts);
      targetMetadata = lib.mapAttrs (_: product: {
        abi = "c";
        inherit (product) exports initializeSymbol;
        runtime = {
          kind = "lean";
          lifecycle = "same-thread-process-lifetime";
          path = toString lean4;
          version = lean4.version;
        };
      }) nativeProducts;
      system = stdenv.hostPlatform.system;
      inherit runCommand python3;
    }
  );
  project = builtProject // {
    inherit projections;
  };
  release =
    runCommand "lake-native-cache-release"
      {
        nativeBuildInputs = [
          lean4
          gnutar
          gzip
        ];
      }
      ''
        export HOME="$TMPDIR/home" LAKE_NO_CACHE=1 RESERVOIR_API_URL="" LEAN_NUM_THREADS=2
        export TAR_OPTIONS="--sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner"
        mkdir -p "$HOME" "$out" stage
        cp -pr ${project}/. stage/
        chmod -R u+w stage
        lake --packages=${overrides} --dir stage pack "$out/${lock.data.project.name}-${lock.data.project.version}.tgz"
      '';
in
assert lib.assertMsg
  (builtins.all (name: validProduct name nativeProducts.${name}) (builtins.attrNames nativeProducts))
  "nativeProducts requires a declared root Lean library, native artifact/header paths, callable exports and initialization symbol";
assert lib.assertMsg (
  !selected || stdenv.hostPlatform.isLinux
) "Lean nativeProducts currently supports native Linux only";
assert lock.problems == [ ];
{
  packages = {
    default = project;
    inherit project;
    environment = deps.output;
  };
  tests = project;
  inherit release projections;
  fetches = lock.entries;
}
