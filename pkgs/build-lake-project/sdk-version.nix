{ nixpkgsSrc }:
builtins.hashString "sha256" (builtins.readFile (nixpkgsSrc + "/.version") + toString nixpkgsSrc)
