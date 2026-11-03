"""Native Lean configuration, empty graphs, external companions and relocking."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
cli = (
    Path(
        subprocess.check_output(
            ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"],
            text=True,
        ).strip()
    )
    / "bin/lake-purifier"
)

with tempfile.TemporaryDirectory(prefix="lake-capture-proof-") as temporary:
    temporary = Path(temporary)
    root = temporary / "project"
    root.mkdir()
    metadata = root / "lakefile.lean"
    metadata.write_text(
        'import Lake\nopen Lake DSL\npackage empty where\n  version := v!"0.1.0"\n@[default_target]\nlean_exe proof where\n  root := `Main\n'
    )
    (root / "Main.lean").write_text("def main : IO Unit := IO.println 42\n")
    (root / "selection.txt").write_text("tracked native configuration\n")
    companion = temporary / "external.json"

    def call(*args):
        return subprocess.run(
            [cli, *args, "--project", root, "--lock", companion],
            check=True,
            capture_output=True,
            text=True,
        )

    call("lock", "--input", "selection.txt")
    empty = json.loads(companion.read_text())
    assert empty["nodes"] == empty["entries"] == []
    call("prefetch")
    before = companion.read_bytes()
    call("lock")
    assert companion.read_bytes() == before
    metadata.write_text(
        metadata.read_text().replace(
            "package empty where", "package purifierProof where"
        )
        + '\nrequire aesop from git\n  "https://github.com/leanprover-community/aesop.git" @\n  "4a174c490d8707121c4a9290800489f105d85e07"\n'
    )
    for name in ["Main.lean", "PurifierProof.lean"]:
        shutil.copy2(repo / "examples/minimal" / name, root / name)
    # A library declaration is native configuration, not a hand-parsed substitute.
    metadata.write_text(
        metadata.read_text() + "\n@[default_target]\nlean_lib PurifierProof\n"
    )
    assert subprocess.run(
        [cli, "prefetch", "--project", root, "--lock", companion], capture_output=True
    ).returncode
    call("lock", "--update")
    selected = json.loads(companion.read_text())
    assert selected["extraInputs"] == ["selection.txt"]
    assert {n["name"] for n in selected["nodes"]} == {"aesop", "batteries"}
    call("prefetch")
    env = dict(
        os.environ, LAKE_PURIFIER_PROJECT=str(root), LAKE_PURIFIER_LOCK=str(companion)
    )
    subprocess.run([cli.parent / "lake", "build"], cwd=root, env=env, check=True)
    answer = subprocess.check_output(
        [cli.parent / "lake", "exe", "proof"], cwd=root, env=env, text=True
    )
    assert answer.strip() == "42"
    selected["nodes"][0]["native"]["version"] = "9.9.9"
    companion.write_text(json.dumps(selected))
    failed = subprocess.run(
        [cli, "prefetch", "--project", root, "--lock", companion],
        capture_output=True,
        text=True,
    )
    assert failed.returncode and "metadata differs" in failed.stderr, failed

print(
    "Native Lean configuration, capture/update, empty graph and metadata binding passed"
)
