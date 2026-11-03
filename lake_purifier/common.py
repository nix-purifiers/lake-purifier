"""Native Lake metadata, SDK identity and locked input validation."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent.parent
LOCK = "lake-purifier.lock.json"


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def environment():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("LEAN_", "LAKE_", "ELAN_", "RESERVOIR_")):
            env.pop(key, None)
    env.update(
        LEAN_SYSROOT=os.environ["LAKE_PURIFIER_LEAN"],
        LEAN_CC=os.environ["LAKE_PURIFIER_CC"],
        LEAN_NUM_THREADS=os.environ.get("NIX_BUILD_CORES", "2"),
        LAKE_NO_CACHE="1",
        RESERVOIR_API_URL="",
    )
    return env


def inspect(root, cache=None):
    args = [os.environ["LAKE_PURIFIER_INSPECT"], root]
    if cache is not None:
        Path(cache).mkdir(parents=True, exist_ok=True)
        args.append(cache)
    return json.loads(
        run(args, env=environment(), capture_output=True, text=True).stdout
    )


def inputs(root, extra=()):
    toolchain = root / "lean-toolchain"
    if (
        toolchain.exists()
        and toolchain.read_text().strip()
        != "leanprover/lean4:v" + os.environ["LAKE_PURIFIER_LEAN_VERSION"]
    ):
        raise ValueError(
            "lean-toolchain must select the Lean version provided by this purifier"
        )
    files = [
        x
        for x in (
            "lakefile.toml",
            "lakefile.lean",
            "lean-toolchain",
            "lake-manifest.json",
        )
        if (root / x).exists()
    ]
    result = {}
    for name in sorted(set([*files, *extra])):
        path = root / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or path.resolve() != path
            or not path.is_file()
        ):
            raise ValueError(
                "Lock inputs must be regular files inside the project: " + name
            )
        blob = path.read_bytes()
        result[name] = {
            "sha256": hashlib.sha256(blob).hexdigest(),
            "content": blob.decode(),
        }
    return result


def load(root, companion):
    data = json.loads(companion.read_text())
    if data.get("version") != 1 or data.get("purifier") != "lake":
        raise ValueError("Invalid Lake lock")
    if data.get("sdk") != os.environ["LAKE_PURIFIER_SDK_VERSION"]:
        raise ValueError("Lean SDK changed; run lake-purifier lock --update")
    if data["inputs"] != inputs(root, data.get("extraInputs", [])):
        raise ValueError("Lake metadata changed; run lake-purifier lock --update")
    state = root / ".lake-purifier" / "inspection"
    if inspect(root, state) != data["project"]:
        raise ValueError(
            "Native Lake configuration changed; run lake-purifier lock --update"
        )
    return data


def locate():
    selected = os.environ.get("LAKE_PURIFIER_LOCK")
    if selected:
        companion = Path(selected).resolve()
        return Path(
            os.environ.get("LAKE_PURIFIER_PROJECT", companion.parent)
        ).resolve(), companion
    root = next(
        (p for p in (Path.cwd(), *Path.cwd().parents) if (p / LOCK).exists()),
        Path.cwd(),
    )
    return root, root / LOCK
