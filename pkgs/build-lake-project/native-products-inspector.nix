{
  runCommand,
  lean4,
  gcc,
}:
runCommand "lake-native-products-inspector"
  {
    nativeBuildInputs = [
      lean4
      gcc
    ];
  }
  ''
    export LEAN_SYSROOT=${lean4} LEAN_CC=${gcc}/bin/cc
    cp ${./native-products.lean} Products.lean
    lean -o Products.olean -c Products.c Products.lean
    mkdir -p "$out/bin"
    leanc -o "$out/bin/lake-native-products" Products.c -rdynamic -lLake
  ''
