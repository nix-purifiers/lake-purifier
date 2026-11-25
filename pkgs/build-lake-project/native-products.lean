import Lake
import Lake.DSL
import Lake.CLI.Main

open System Lake

def main (args : List String) : IO Unit := do
  let (elan?, lean?, lake?) ← Lake.findInstall?
  let lake? := lake?.orElse (fun _ => lean?.map LakeInstall.ofLean)
  let root ← IO.FS.realPath (args.headD ".")
  let opts : Lake.LakeOptions := {
    rootDir := root
    leanInstall? := lean?
    lakeInstall? := lake?
    elanInstall? := elan?
    noCache := true
  }
  let cfg ← opts.mkLoadConfig |>.toIO (fun e => IO.userError s!"{repr e}")
  let some ws ← (Lake.loadWorkspaceRoot cfg).toBaseIO
    | throw <| IO.userError "Native Lake package metadata failed"
  IO.println <| Lean.Json.compress <| Lean.Json.mkObj [
    ("root", Lean.toJson root.toString),
    ("package", Lean.toJson ws.root.baseName.toString),
    ("defaultTargets", Lean.toJson (ws.root.defaultTargets.map (·.toString))),
    ("targets", Lean.toJson (ws.root.targetDecls.map (·.name.toString))),
    ("libraries", Lean.Json.arr (ws.root.leanLibs.map fun library => Lean.Json.mkObj [
      ("name", Lean.toJson library.name.toString),
      ("nativeName", Lean.toJson library.libName),
      ("defaultFacets", Lean.toJson (library.defaultFacets.map (·.toString))),
      ("defaultShared", Lean.toJson (library.defaultFacets.contains LeanLib.sharedFacet)),
      ("sharedLibrary", Lean.toJson library.sharedLibFile.toString)
    ]))
  ]
