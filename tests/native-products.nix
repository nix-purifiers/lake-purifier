{
  pkgs,
  src ? ./fixtures/native,
  expected ? 41,
}:
let
  product = pkgs.lake-purifier.buildLeanProject {
    inherit src;
    nativeProducts.Native = {
      target = "foreign";
      library = ".lake/build/lib/libnativeProjectionProof_ffi.so";
      header = "api.h";
      initializeSymbol = "projection_initialize";
      exports = [ "projection_answer" ];
    };
  };
  python = pkgs.python3.withPackages (p: [ p.cffi ]);
  producer = product.packages.project;
  library = "${producer}/.lake/build/lib/libnativeProjectionProof_ffi.so";
in
pkgs.runCommand "lake-native-foreign-consumers"
  {
    passthru = {
      inherit producer;
      projection = product.projections.native;
    };
    nativeBuildInputs = [
      python
      pkgs.gcc
      pkgs.jdk21
    ];
  }
  ''
    python ${./native-consumers.py} ${product.projections.native}/catalog.json ${toString expected}
    cc ${./native-consumer.c} -DEXPECTED=${toString expected} -I${producer}/include/lake-native/Native ${library} -o consume
    ./consume
    cp ${./NativeConsumer.java} NativeConsumer.java
    javac --enable-preview --release 21 NativeConsumer.java
    java --enable-preview --enable-native-access=ALL-UNNAMED NativeConsumer ${library} ${toString expected}
    mkdir -p "$out"
    cp ${producer}/nix-support/lake-native/verified-products.json "$out/"
  ''
