{
  project,
  companion,
  target ? "environment",
  sdk ? null,
  profile ? false,
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  purifier = import (/. + "@purifier@/nix/lib") { inherit (pkgs) lib; };
  nativeInspector = pkgs.callPackage ./native.nix { };
  sdkVersion = import ./sdk-version.nix { inherit nixpkgsSrc; };
  build = pkgs.callPackage ./default.nix { inherit purifier nativeInspector sdkVersion; } {
    src = /. + project;
    lockFile = /. + companion;
  };
  output =
    if target == "environment" then
      build.packages.environment
    else if target == "release" then
      build.release
    else
      throw "Unknown Lake target";
in
if profile then
  pkgs.writeText "lake-${target}-profile.json" (
    builtins.toJSON {
      inherit output;
      sdk = builtins.storePath sdk;
    }
  )
else
  output
