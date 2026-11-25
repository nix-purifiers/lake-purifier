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

## Native foreign-library projections

`nativeProducts` selects an explicitly declared root Lean library and its native
shared artifact. The library must expose a caller-authored C API, including an
initialization function and a matching public header:

```nix
pkgs.lake-purifier.buildLeanProject {
  src = ./.;
  nativeProducts.Native = {
    target = "foreign";
    library = ".lake/build/lib/libnativeProjectionProof_ffi.so";
    header = "api.h";
    initializeSymbol = "projection_initialize";
    exports = [ "projection_answer" ];
  };
}
```

`target` optionally names a caller-authored root Lake target returning an
artifact path. The builder uses native `lake query --json` to verify that path.
Without `target`, it selects the declared library's native `:shared` facet and
checks the path reported by the original Lake API. Native library and module
initializer names remain unchanged; the purifier generates no C ABI wrappers or
signatures.

Linux Lean plugin libraries normally leave dependencies to the Lean host.
Foreign consumers need a standalone native link closure instead. The fixture's
authored Lake target uses the original `buildLeanSharedLib` with `linkDeps := true`
and links the original shared Lean runtime. Selected dependencies are prepared
with both their captured static targets and corresponding native shared facets.
Wrapped `lake build` also prepares shared dependencies for explicit `:shared`
requests and native library declarations selecting the shared default facet.

Both the result and `packages.project` expose `projections.native`,
`projections.python-ffi` and `projections.java-ffi`, including a catalog, lazy
ctypes loader and Java library-path arguments. Authored headers are installed
under `include/lake-native/<library>`; `include/lean` retains the original SDK
headers. The checks bind actual native target paths, callable exports, original
runtime, caller sources and installed bytes. Native compiler setup metadata is
retained under `nix-support/lake-native` before the generic installation removes
its working copies.

Initialize before calling the exported API, use that native thread for calls,
and keep the library loaded for the process lifetime. Callers supply compatible
signatures and manage ownership of Lean values crossing their C API. Loading
does not initialize the runtime automatically. The current consumer fixture
uses unboxed `UInt32` values and allocation-heavy Lean lists; it does not prove
foreign-thread attachment, unloading or arbitrary boxed-object ownership.
Local validation uses Lean 4.35 on x86_64 Linux and JDK 21's preview FFM API.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
