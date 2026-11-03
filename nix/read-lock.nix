{ lib }:
{
  src,
  lockFile ? src + "/lake-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  nodes = data.nodes or [ ];
  safe =
    s: builtins.isString s && s != "." && s != ".." && builtins.match "[A-Za-z0-9_.-]+" s != null;
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  native =
    n:
    builtins.isAttrs n
    && safe (n.name or null)
    && builtins.isString (n.version or null)
    && builtins.all (k: builtins.isList (n.${k} or null) && builtins.all builtins.isString n.${k}) [
      "libraries"
      "dependencies"
      "defaultTargets"
    ];
  valid =
    (data.version or null) == 1
    && (data.purifier or null) == "lake"
    && builtins.isString (data.sdk or null)
    && builtins.isString (data.leanVersion or null)
    && builtins.match "[A-Za-z0-9.+-]+" data.leanVersion != null
    && native (data.project or null)
    && builtins.isList entries
    && builtins.isList nodes
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs
    && builtins.isAttrs (data.inputs or null)
    &&
      builtins.attrNames data.inputs == builtins.sort builtins.lessThan (
        lib.unique (
          (builtins.filter (name: builtins.pathExists (src + "/${name}")) [
            "lakefile.toml"
            "lakefile.lean"
            "lean-toolchain"
            "lake-manifest.json"
          ])
          ++ data.extraInputs
        )
      )
    && data.inputs ? "lake-manifest.json"
    && (data.inputs ? "lakefile.toml" || data.inputs ? "lakefile.lean")
    && (
      !(data.inputs ? "lean-toolchain")
      || builtins.elem data.inputs."lean-toolchain".content [
        "leanprover/lean4:v${data.leanVersion}"
        "leanprover/lean4:v${data.leanVersion}\n"
      ]
    )
    && builtins.all (
      name:
      relative name
      && builtins.isAttrs data.inputs.${name}
      && builtins.isString (data.inputs.${name}.content or null)
      && builtins.pathExists (src + "/${name}")
      && (builtins.readDir (dirOf (src + "/${name}"))).${baseNameOf name} == "regular"
      && builtins.hashFile "sha256" (src + "/${name}") == (data.inputs.${name}.sha256 or null)
      && builtins.hashString "sha256" data.inputs.${name}.content == data.inputs.${name}.sha256
    ) (builtins.attrNames data.inputs)
    && builtins.all (
      e:
      builtins.isAttrs e
      && relative (e.path or null)
      && lib.hasPrefix "git/" e.path
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && builtins.isAttrs (e.git or null)
      && builtins.isString (e.git.url or null)
      && builtins.isString (e.git.rev or null)
      && builtins.match "[0-9a-f]{40}" e.git.rev != null
      && (e.git.submodules or null) == false
      && (e.git.leaveDotGit or null) == false
      && e.git ? commitObject
      && e.git.commitObject == null
      && !(e ? url)
    ) entries
    && builtins.all (
      n:
      builtins.isAttrs n
      && safe (n.name or null)
      && native (n.native or null)
      && n.native.name == n.name
      && (n.entry or null) == "git/${n.name}"
      && builtins.isList (n.targets or null)
      && builtins.all (
        t: builtins.isString t && builtins.match "[A-Za-z0-9_.]+:static" t != null
      ) n.targets
      && builtins.any (e: e.path == n.entry) entries
      && builtins.all (d: builtins.any (other: other.name == d) nodes) n.native.dependencies
    ) nodes
    && builtins.length nodes == builtins.length entries
    && builtins.length (lib.unique (map (n: n.name) nodes)) == builtins.length nodes
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries
    && builtins.all (d: builtins.any (n: n.name == d) nodes) data.project.dependencies;
in
{
  purifier = "lake";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "Lake lock is missing, stale, or unsupported; run lake-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
