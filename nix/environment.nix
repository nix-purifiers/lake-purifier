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
}:
{
  lock,
  fetchers ? { },
  nativeBuildInputs ? [ ],
}:
let
  checked = purifier.checkLock lock;
  data = checked.data;
  tree = purifier.tree (
    {
      name = "lake-fixed-sources";
      entries = checked.entries;
      inherit
        runCommand
        fetchgit
        python3
        writeText
        ;
    }
    // fetchers
  );
  packages = builtins.listToAttrs (
    map (node: {
      name = node.name;
      value = buildLakePackage {
        pname = "purified-lake-${node.name}";
        version = node.native.version;
        src = tree + "/${node.entry}";
        unpackPhase = ''
          mkdir source
          cp -prL "$src"/. source/
          chmod -R u+w source
          sourceRoot=source
        '';
        leanPackageName = node.name;
        leanDeps = map (name: packages.${name}) node.native.dependencies;
        buildTargets = node.targets;
        inherit nativeBuildInputs;
        preConfigure = ''
          export LEAN_SYSROOT=${lean4}
          export LEAN_CC=${gcc}/bin/cc
          ${nativeInspector}/bin/lake-inspect "$PWD" > "$TMPDIR/native.json"
          ${python3}/bin/python3 ${../lake_purifier/check-metadata.py} ${writeText "lake-node.json" (builtins.toJSON node.native)} "$TMPDIR/native.json"
        '';
        postConfigure = "export LEAN_NUM_THREADS=2";
      };
    }) data.nodes
  );
  overrides = {
    schemaVersion = "1.2.0";
    packages = map (node: {
      type = "path";
      name = node.name;
      inherited = false;
      dir = toString packages.${node.name};
    }) data.nodes;
  };
  output = writeText "lake-environment.json" (
    builtins.toJSON {
      inherit overrides;
      packages = map (n: packages.${n.name}) data.nodes;
    }
  );
in
assert checked.problems == [ ];
assert lib.assertMsg (data.sdk == sdkVersion) "Lean SDK changed; update the lock";
assert lib.assertMsg (data.leanVersion == lean4.version) "Lean version changed; update the lock";
{
  inherit output packages;
}
