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
  let cfg ← if let some directory := args[1]? then
    pure {cfg with wsDir := (← IO.FS.realPath (FilePath.mk directory))}
    else pure cfg
  let some ws ← (Lake.loadWorkspaceRoot cfg).toBaseIO
    | throw <| IO.userError "Native Lake package metadata failed"
  IO.println <| Lean.Json.compress <| Lean.Json.mkObj [
    ("name", Lean.toJson ws.root.baseName.toString),
    ("version", Lean.toJson (toString ws.root.version)),
    ("libraries", Lean.toJson (ws.root.leanLibs.map (fun x => x.name.toString))),
    ("dependencies", Lean.toJson (ws.root.depConfigs.map (fun x => x.name.toString))),
    ("defaultTargets", Lean.toJson (ws.root.defaultTargets.map (fun x => x.toString)))
  ]
