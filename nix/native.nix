{
  runCommand,
  lean4,
  gcc,
}:
runCommand "lake-native-inspector"
  {
    nativeBuildInputs = [
      lean4
      gcc
    ];
  }
  ''
    export LEAN_SYSROOT=${lean4}
    cp ${../lake_purifier/inspect.lean} inspect.lean
    lean -o inspect.olean -c inspect.c inspect.lean
    mkdir -p "$out/bin"
    leanc -o "$out/bin/lake-inspect" inspect.c -rdynamic -lLake
  ''
