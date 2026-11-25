"""Real native builds must reject wrong exports, artifacts and installed sources."""
import json
import os
from pathlib import Path
import subprocess

repo = Path(__file__).resolve().parent.parent
core = os.environ.get("LAKE_TEST_CORE_SOURCE")
builder = "p.lake-purifier.buildLeanProject"
if core:
    builder += ".override {purifier=import ((/. + " + json.dumps(core) + ") + \"/nix/lib\") {inherit(p) lib;};}"
prefix = "let f=builtins.getFlake " + json.dumps(str(repo)) + ";p=import f.inputs.nixpkgs {overlays=[f.overlays.default];};build=" + builder + ";in (build {src=" + str(repo / "tests/fixtures/native") + ";"
base = {"target": "foreign", "library": ".lake/build/lib/libnativeProjectionProof_ffi.so",
        "header": "api.h", "initializeSymbol": "projection_initialize",
        "exports": ["projection_answer"]}
cases = [
    ({**base, "exports": ["missing_projection_answer"]}, "", "native callable exports missing"),
    ({**base, "library": ".lake/build/lib/libwrong.so"}, "", "selected artifact differs"),
    (base, 'installPhase = \'\'mkdir -p "$out"; cp -rT . "$out"; echo changed >> "$out/Native.lean";\'\';',
     "authored producer source changed"),
]
for product, extra, message in cases:
    fields = " ".join(key + "=" + (json.dumps(value) if not isinstance(value, list)
        else "[" + " ".join(map(json.dumps, value)) + "]") + ";" for key, value in product.items())
    expression = prefix + "nativeProducts.Native={" + fields + "};" + extra + "}).packages.project"
    result = subprocess.run(["nix", "build", "--impure", "--expr", expression, "--no-link", "-L"],
                            capture_output=True, text=True)
    assert result.returncode != 0 and message in result.stderr, result.stderr
    print(message + " rejected by actual native build")
