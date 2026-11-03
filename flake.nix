{
  description = "Locked, Nix-resolved Lean and Lake dependencies";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        lake-purifier = final.lib.makeScope final.newScope (scope: {
          nativeInspector = scope.callPackage ./nix/native.nix { };
          sdkVersion = import ./nix/sdk-version.nix { nixpkgsSrc = nixpkgs; };
          cli = scope.callPackage ./nix/cli.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildLeanProject = scope.callPackage ./nix/build-project.nix {
            purifier = import (purifier + "/nix/lib") { inherit (final) lib; };
          };
        });
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).lake-purifier.cli;
        cli = self.packages.${system}.default;
        sdk = (pkgsFor system).lean4;
      });
      lib.lake-purifier.readLock = import ./nix/read-lock.nix { lib = nixpkgs.lib; };
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/lake-purifier";
          meta.description = "Lock native Lean dependencies";
        };
      });
      checks = forAll (
        system:
        let
          pkgs = pkgsFor system;
          build = pkgs.lake-purifier.buildLeanProject {
            src = ./examples/minimal;
            doCheck = true;
            checkPhase = ".lake/build/bin/proof | grep -Fx 42";
          };
        in
        {
          inherit (build.packages) environment project;
          release = build.release;
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
