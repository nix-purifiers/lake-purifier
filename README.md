# lake-purifier

Locked, Nix-resolved dependencies for Lean and Lake.

## Quickstart

Start in a Lake project using the supplied Lean version.

```sh
nix shell 'github:nix-purifiers/lake-purifier'
lake-purifier lock
lake build
lake exe your-program
```

The shell supplies a Lake wrapper and pinned Lean compiler. Dependencies are
compiled by Nix; Lake reuses their readonly `.olean` files and native libraries
while compiling your source in its normal `.lake/build` directory. Both
`lakefile.toml` and `lakefile.lean` are supported.

Without a companion lockfile, the wrapper warns and runs ordinary, impure Lake.
A stale or invalid lock fails. Commit `lake-manifest.json` and
`lake-purifier.lock.json`. Refresh dependency selection with:

```sh
lake-purifier lock --update
```

Source edits do not require relocking. Track additional configuration inputs
with `lock --input path`. `prefetch` prepares the compiled dependencies. The
wrapper can also be installed using your normal Nix configuration.

## Native tooling

```sh
lake env lean MyModule.lean
lake serve
```

Lake's environment and language server use the same Nix dependency paths as the
compiler. Dependency source remains available for navigation. An existing local
package checkout or cache does not select dependencies in a locked session.

## Scope

The native Lake resolver selects the transitive Git graph. The companion records
exact revisions, Nix source hashes, native package metadata, build targets,
configuration inputs and SDK identity. Dependency metadata is checked again
before compilation. The prepared environment supplies native `--packages`
overrides for the entire graph.

This version supports Lean 4.35.0 and Git dependencies without subdirectories.
Local dependency workspaces, alternate toolchains, Reservoir release downloads
and arbitrary extra downloads in custom build scripts are outside its current
scope. Use `leanprover/lean4:v4.35.0` in `lean-toolchain`. Dependency libraries
selected by their native default targets are compiled with the `static` facet;
if no library is a default target, all declared libraries are prepared.

## Build caches and publication

```sh
lake-purifier bundle
lake-purifier publish --tag v0.1.0
```

`bundle` produces a reproducible native Lake build-cache archive. A matching
source checkout can consume it with `lake unpack path/to/archive.tgz`.
`publish` uploads those exact bytes to an existing GitHub release using Lake's
`gh release upload` protocol. It does not create a source release or publish to
Reservoir.

Use `--project` and `--lock` for an external companion. Native commands accept
`LAKE_PURIFIER_PROJECT` and `LAKE_PURIFIER_LOCK`. Environment profiles retain the
compiled dependencies and wrapper SDK as Nix garbage collector roots.

## Building with Nix

An optional project definition can use the overlay's named builder:

```nix
pkgs.lake-purifier.buildLeanProject {
  src = ./.;
  doCheck = true;
  checkPhase = ".lake/build/bin/my-tests";
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
`packages.environment` describes the compiled dependencies;
`packages.project` contains the complete compiled package. Override
`buildTargets`, `nativeBuildInputs` or `installPhase` for the project.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
