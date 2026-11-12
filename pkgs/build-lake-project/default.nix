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
}:
let
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } { inherit src lockFile; }
  );
  deps = import ./environment.nix (builtins.removeAttrs scope [
    "gnutar"
    "gzip"
  ]) { inherit lock fetchers nativeBuildInputs; };
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
  project = buildLakePackage (
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
      inherit
        buildTargets
        nativeBuildInputs
        doCheck
        checkPhase
        ;
      preConfigure = ''
        export LEAN_SYSROOT=${lean4}
        export LEAN_CC=${gcc}/bin/cc
        ${nativeInspector}/bin/lake-inspect "$PWD" > "$TMPDIR/native.json"
        ${python3}/bin/python3 ${../../lake_purifier/check-metadata.py} ${expected} "$TMPDIR/native.json"
      '';
      postConfigure = "export LEAN_NUM_THREADS=2";
    }
    // lib.optionalAttrs (installPhase != null) { inherit installPhase; }
  );
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
assert lock.problems == [ ];
{
  packages = {
    default = project;
    inherit project;
    environment = deps.output;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
