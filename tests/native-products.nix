{ pkgs }:
let
  product = pkgs.lake-purifier.buildLeanProject {
    src = ./fixtures/native;
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
    nativeBuildInputs = [
      python
      pkgs.gcc
      pkgs.jdk21
    ];
  }
  ''
    python ${./native-consumers.py} ${product.projections.native}/catalog.json
    cc ${./native-consumer.c} -I${producer}/include/lake-native/Native ${library} -o consume
    ./consume
    cp ${./NativeConsumer.java} NativeConsumer.java
    javac --enable-preview --release 21 NativeConsumer.java
    java --enable-preview --enable-native-access=ALL-UNNAMED NativeConsumer ${library}
    mkdir -p "$out"
    cp ${producer}/nix-support/lake-native/verified-products.json "$out/"
  ''
