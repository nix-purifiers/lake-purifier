"""Native Lake commands using compiled, Nix-resolved dependencies."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from .capture import capture
from .common import HERE, environment, load, locate, run


def realize(root, companion, target="environment"):
    state = root / ".lake-purifier"
    state.mkdir(exist_ok=True)
    profile = state / (target + "-profile")
    result = run(
        [
            "nix-build",
            HERE / "pkgs/build-lake-project/realize.nix",
            "--argstr",
            "project",
            root,
            "--argstr",
            "companion",
            companion,
            "--argstr",
            "target",
            target,
            "--argstr",
            "sdk",
            os.environ["LAKE_PURIFIER_SDK"],
            "--arg",
            "profile",
            "true",
            "--out-link",
            profile,
        ],
        capture_output=True,
        text=True,
    )
    return Path(
        json.loads(Path(result.stdout.strip().splitlines()[-1]).read_text())["output"]
    )


def native(args):
    # Resolve Lake's native directory selector before locating the companion.
    args = list(args)
    selected = None
    for i, value in enumerate(args):
        if value in ("--dir", "-d"):
            if i + 1 >= len(args):
                raise ValueError("Missing Lake project directory")
            selected = args[i + 1]
            del args[i : i + 2]
            break
        if value.startswith("--dir="):
            selected = value.split("=", 1)[1]
            del args[i]
            break
    if selected is not None:
        os.chdir(selected)
    root, companion = locate()
    if not companion.exists():
        print(
            "warning: lake-purifier: no lockfile; using ordinary impure Lake resolution",
            file=sys.stderr,
        )
        os.execv(os.environ["LAKE_PURIFIER_NATIVE"], ["lake", *args])
    load(root, companion)
    if any(
        x in ("update", "--update", "-U", "-f", "--config", "-d", "--dir")
        or x.startswith(
            ("--packages", "--override", "--lean", "--lake", "--config=", "--dir=")
        )
        for x in args
    ):
        raise ValueError(
            "Locked Lake resolution cannot be overridden; run lake-purifier lock --update"
        )
    env_file = realize(root, companion)
    env_data = json.loads(env_file.read_text())
    digest = hashlib.sha256(env_file.read_bytes()).hexdigest()
    session = root / ".lake-purifier" / digest
    session.mkdir(parents=True, exist_ok=True)
    overrides = session / "overrides.json"
    overrides.write_text(json.dumps(env_data["overrides"]))
    env = environment()
    os.execve(
        os.environ["LAKE_PURIFIER_NATIVE"],
        [
            "lake",
            "--dir",
            str(root),
            "--packages=" + str(overrides),
            "--no-cache",
            *args,
        ],
        env,
    )


def main():
    try:
        args = sys.argv[1:]
        if args[:1] == ["--native"]:
            native(args[1:])
            return
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "command", choices=["lock", "prefetch", "bundle", "publish"]
        )
        parser.add_argument("--update", action="store_true")
        parser.add_argument("--input", action="append", default=[])
        parser.add_argument("--project", type=Path, default=Path.cwd())
        parser.add_argument("--lock", type=Path)
        parser.add_argument("--tag")
        opts = parser.parse_args(args)
        root = opts.project.resolve()
        companion = (
            opts.lock.resolve() if opts.lock else root / "lake-purifier.lock.json"
        )
        if opts.command == "lock":
            capture(root, companion, opts.update, opts.input)
        else:
            data = load(root, companion)
            result = realize(
                root,
                companion,
                "environment" if opts.command == "prefetch" else "release",
            )
            if opts.command == "publish":
                if not opts.tag:
                    raise ValueError("Native Lake cache publication requires --tag")
                archive = result / (
                    data["project"]["name"] + "-" + data["project"]["version"] + ".tgz"
                )
                # Use Lake's native release-upload protocol with the realized bytes.
                run(
                    [
                        os.environ.get("LAKE_PURIFIER_GH", "gh"),
                        "release",
                        "upload",
                        opts.tag,
                        archive,
                        "--clobber",
                    ],
                    cwd=root,
                )
            print(result)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        print("lake-purifier: " + str(error), file=sys.stderr)
        raise SystemExit(1)
