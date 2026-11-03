{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  git,
  nix-prefetch-git,
  lean4,
  gcc,
  gnutar,
  gzip,
  cacert,
  nativeInspector,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "lake-purifier";
  version = "0.1.0";
  src = ../.;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/lake-purifier"
    cp -r lake_purifier nix "$out/lib/lake-purifier/"
    install -m755 bin/lake-purifier "$out/bin/lake-purifier"
    substituteInPlace "$out/lib/lake-purifier/nix/realize.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    wrapProgram "$out/bin/lake-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          git
          nix-prefetch-git
          lean4
          gcc
          gnutar
          gzip
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default LAKE_PURIFIER_GH ${gh}/bin/gh \
      --set LAKE_PURIFIER_NATIVE ${lean4}/bin/lake \
      --set LAKE_PURIFIER_LEAN ${lean4} \
      --set LAKE_PURIFIER_LEAN_VERSION ${lean4.version} \
      --set LAKE_PURIFIER_CC ${gcc}/bin/cc \
      --set LAKE_PURIFIER_INSPECT ${nativeInspector}/bin/lake-inspect \
      --set LAKE_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set LAKE_PURIFIER_SDK "$out"
    makeWrapper "$out/bin/lake-purifier" "$out/bin/lake" --add-flags '--native'
    ln -s ${lean4}/bin/lean "$out/bin/lean"
    ln -s ${lean4}/bin/leanc "$out/bin/leanc"
  '';
  meta = {
    description = "Native Lean and Lake workflow with locked Nix-resolved dependencies";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "lake-purifier";
  };
}
