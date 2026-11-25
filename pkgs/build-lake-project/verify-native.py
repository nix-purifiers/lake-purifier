"""Join native Lake metadata, compiler artifacts, authored sources and runtime."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if sys.argv[1] == "capture":
    source, destination = map(Path, sys.argv[2:])
    records = {str(path.relative_to(source)): digest(path)
               for path in sorted(source.rglob("*")) if path.is_file()}
    destination.write_text(json.dumps(records, sort_keys=True) + "\n")
    raise SystemExit(0)

working, installed, catalog, inventory, specification, sdk, nm, ldd, queries_file = sys.argv[2:]
working, installed, sdk = map(lambda value: Path(value).resolve(), [working, installed, sdk])
native = json.loads(Path(catalog).read_text())
sources = json.loads(Path(inventory).read_text())
spec = json.loads(Path(specification).read_text())
libraries = {library["name"]: library for library in native["libraries"]}
queries = json.loads(Path(queries_file).read_text())
if Path(native["root"]).resolve() != working:
    raise ValueError("native metadata belongs to another producer")
for name, expected in sources.items():
    for root in [working, installed]:
        if digest(root / name) != expected:
            raise ValueError("authored producer source changed: " + name)
proofs = {}
for name, product in spec.items():
    if "target" in product:
        if product["target"] not in native["targets"]:
            raise ValueError("standalone target is not declared by the root producer")
        original = Path(queries[name]["path"]).resolve(strict=True)
    else:
        original = Path(libraries[name]["sharedLibrary"]).resolve(strict=True)
    relative = original.relative_to(working)
    if relative != Path(product["library"]):
        raise ValueError("selected artifact differs from native Lake library")
    library = installed / relative
    if not library.resolve(strict=True).is_relative_to(installed):
        raise ValueError("installed library escapes the producer")
    if original.read_bytes() != library.read_bytes():
        raise ValueError("installed native library bytes changed")
    output = subprocess.check_output([nm, "-D", "--defined-only", str(library)], text=True)
    symbols = {parts[-1] for line in output.splitlines()
               if len(parts := line.split()) >= 3 and parts[-2] in {"T", "W"}}
    missing = set(product["exports"] + [product["initializeSymbol"]]) - symbols
    if missing:
        raise ValueError("native callable exports missing: " + repr(sorted(missing)))
    env = {key: value for key, value in os.environ.items() if not key.startswith("LD_")}
    loaded = subprocess.check_output([ldd, str(library)], env=env, text=True)
    runtime = sdk / "lib/lean/libleanshared.so"
    if "not found" in loaded or str(runtime) not in loaded:
        raise ValueError("original Lean shared runtime is not resolved")
    # Resolve the actual native graph. This does not call the authored initializer.
    subprocess.run([sys.executable, "-c",
        "import ctypes,sys; p=ctypes.CDLL(sys.argv[1]); [getattr(p,s) for s in sys.argv[2:]]",
        str(library), *product["exports"], product["initializeSymbol"]], check=True, env=env)
    header = Path(product["header"])
    if str(header) not in sources or not (working / header).resolve().is_relative_to(working):
        raise ValueError("public header is not an authored producer file")
    include = installed / "include/lake-native" / name
    include.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(working / header, include / header.name)
    proofs[name] = {"native": libraries[name], "relativeLibrary": str(relative),
                    "sha256": digest(library), "headerSha256": digest(include / header.name),
                    "runtime": str(runtime), "runtimeSha256": digest(runtime),
                    "nativeDependencies": loaded}
support = installed / "nix-support/lake-native"
support.mkdir(parents=True, exist_ok=True)
shutil.copyfile(catalog, support / "native-products.json")
shutil.copyfile(inventory, support / "authored-inputs.json")
shutil.copyfile(queries_file, support / "native-queries.json")
for path in (working / ".lake/build/ir").rglob("*.setup.json"):
    destination = support / "setup" / path.relative_to(working / ".lake/build/ir")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
(support / "verified-products.json").write_text(json.dumps(proofs, sort_keys=True) + "\n")
