import Lake
open System Lake DSL
package nativeProjectionProof where
  version := v!"0.1.0"
require batteries from git "https://github.com/leanprover-community/batteries" @ "66e469188fe07963e5cf666c7d4433f45b8131c5"
input_file host.c where
  path := "host.c"
  text := true
target host.o pkg : FilePath := do
  let srcJob ← host.c.fetch
  let includeDir ← getLeanIncludeDir
  buildO (pkg.buildDir / "host.o") srcJob #["-I", includeDir.toString]
    #["-fPIC", "-DLEAN_EXPORTING"] "cc" getLeanTrace
@[default_target]
lean_lib Native where
  defaultFacets := #[LeanLib.sharedFacet]
  moreLinkObjs := #[host.o]
  moreLinkArgs := #["-lleanshared"]

@[default_target]
target foreign pkg : Dynlib := do
  let some lib := pkg.leanLibs.find? (fun library => library.name == `Native)
    | error "Native root library not found"
  let mods ← (← lib.modules.fetch).await
  let objects ← mods.flatMapM fun mod =>
    mod.nativeFacets true |>.mapM (·.fetch mod)
  let moreObjects ← lib.moreLinkObjs.mapM (·.fetchIn pkg)
  let native ← (← lib.shared.fetch).await
  buildLeanSharedLib "nativeProjectionProof_ffi"
    (pkg.sharedLibDir / nameToSharedLib "nativeProjectionProof_ffi")
    (objects ++ moreObjects) (native.deps.map Job.pure)
    #[] #["-lleanshared", "-Wl,-z,defs"] (linkDeps := true)
