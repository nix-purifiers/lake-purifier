"""Validate the lock protocol without import-from-derivation."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "source"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".lake", ".lake-purifier"),
    )
    companion = root / "lake-purifier.lock.json"
    original = json.loads(companion.read_text())

    def inspect():
        expression = f"let f=builtins.getFlake {json.dumps(str(repo))};lock=f.lib.lake-purifier.readLock {{src=/. + {json.dumps(str(root))};}};in {{inherit(lock) problems outputs;fetches=map(e: e.path)lock.entries;}}"
        return json.loads(
            subprocess.check_output(
                [
                    "nix",
                    "eval",
                    "--impure",
                    "--json",
                    "--option",
                    "allow-import-from-derivation",
                    "false",
                    "--expr",
                    expression,
                ],
                text=True,
            )
        )

    valid = inspect()
    assert valid["problems"] == [] and valid["outputs"]["packages"] == [
        "default",
        "environment",
        "project",
    ]
    companion.unlink()
    assert inspect()["problems"]
    for mutation in [
        lambda d: d.update(purifier="other"),
        lambda d: d["entries"][0]["git"].update(rev="invalid"),
        lambda d: d["entries"][0].update(hash="invalid"),
        lambda d: d["nodes"][0].update(targets=["injected;command"]),
        lambda d: d["nodes"][0]["native"].update(dependencies=["missing"]),
        lambda d: d.update(sdk=None),
        lambda d: d.update(leanVersion="wrong"),
    ]:
        data = json.loads(json.dumps(original))
        mutation(data)
        companion.write_text(json.dumps(data))
        assert inspect()["problems"]
    companion.write_text(json.dumps(original))
    (root / "lakefile.lean").write_text("-- additional untracked configuration\n")
    assert inspect()["problems"]
    (root / "lakefile.lean").unlink()
    (root / "lakefile.toml").write_text("# stale\n")
    assert inspect()["problems"]

print("Lake lock validation passed without IFD")
