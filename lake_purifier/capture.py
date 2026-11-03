"""Resolve with Lake, then retain native Git coordinates and fixed source hashes."""

import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from .common import environment, inputs, inspect, load, run


def capture(root, companion, update=False, extra=()):
    if companion.exists() and not update:
        load(root, companion)
        return
    if companion.exists() and update and not extra:
        try:
            extra = json.loads(companion.read_text()).get("extraInputs", [])
        except (ValueError, AttributeError):
            pass
    with tempfile.TemporaryDirectory(prefix="lake-capture-") as temporary:
        temporary = Path(temporary)
        staged = temporary / "source"
        shutil.copytree(
            root,
            staged,
            ignore=shutil.ignore_patterns(
                ".git", ".lake", ".lake-purifier", "result*", "__pycache__"
            ),
        )
        env = environment()
        home = temporary / "home"
        home.mkdir()
        env.update(
            HOME=str(home),
            XDG_CACHE_HOME=str(home / "cache"),
            XDG_CONFIG_HOME=str(home / "config"),
        )
        run(
            [os.environ["LAKE_PURIFIER_NATIVE"], "--keep-toolchain", "update"],
            cwd=staged,
            env=env,
        )
        manifest_path = staged / "lake-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if (
            manifest.get("version") != "1.3.0"
            or manifest.get("packagesDir") != ".lake/packages"
        ):
            raise ValueError("Unsupported native Lake manifest layout")
        entries, nodes = [], []
        for package in manifest["packages"]:
            name = package["name"]
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in (".", ".."):
                raise ValueError("Unsupported Lake package name")
            if package["type"] != "git" or package.get("subDir") is not None:
                raise ValueError(
                    "This integration currently requires Git packages without subdirectories"
                )
            if not re.fullmatch(r"[0-9a-f]{40}", package["rev"]):
                raise ValueError("Lake did not resolve a full Git revision")
            fetched = json.loads(
                run(
                    [
                        "nix-prefetch-git",
                        "--url",
                        package["url"],
                        "--rev",
                        package["rev"],
                        "--quiet",
                    ],
                    capture_output=True,
                    text=True,
                ).stdout
            )
            native = inspect(Path(fetched["path"]), temporary / "metadata" / name)
            if native["name"] != name:
                raise ValueError(
                    "Native Lake package identity differs from the manifest"
                )
            libraries = [
                x for x in native["libraries"] if x in native["defaultTargets"]
            ] or native["libraries"]
            nodes.append(
                {
                    "name": name,
                    "entry": "git/" + name,
                    "native": native,
                    "targets": [x + ":static" for x in libraries],
                }
            )
            sri = run(
                [
                    "nix",
                    "hash",
                    "convert",
                    "--hash-algo",
                    "sha256",
                    "--to",
                    "sri",
                    fetched["sha256"],
                ],
                capture_output=True,
                text=True,
            ).stdout.strip()
            checkout = staged / ".lake/packages" / name
            retained = temporary / "native-sources" / name
            retained.mkdir(parents=True)
            tracked = run(
                ["git", "-C", checkout, "ls-files", "-z"],
                capture_output=True,
                text=True,
            ).stdout
            for filename in tracked.split("\0"):
                if filename:
                    target = retained / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(checkout / filename, target, follow_symlinks=False)
            native_hash = run(
                ["nix", "hash", "path", "--sri", retained],
                capture_output=True,
                text=True,
            ).stdout.strip()
            if native_hash != sri:
                raise ValueError(
                    "Native Lake checkout differs from its fixed Git source: " + name
                )
            entries.append(
                {
                    "path": "git/" + name,
                    "hash": sri,
                    "git": {
                        "url": package["url"],
                        "rev": package["rev"],
                        "submodules": False,
                        "leaveDotGit": False,
                        "commitObject": None,
                    },
                }
            )
        names = {x["name"] for x in nodes}
        native_root = inspect(staged)
        if any(
            d not in names
            for n in [native_root, *(n["native"] for n in nodes)]
            for d in n["dependencies"]
        ):
            raise ValueError("Native Lake dependency graph is incomplete")
        # Commit the exact manifest produced by Lake together with its companion.
        (root / "lake-manifest.json").write_bytes(manifest_path.read_bytes())
        data = {
            "version": 1,
            "purifier": "lake",
            "sdk": os.environ["LAKE_PURIFIER_SDK_VERSION"],
            "leanVersion": os.environ["LAKE_PURIFIER_LEAN_VERSION"],
            "project": native_root,
            "extraInputs": list(extra),
            "inputs": inputs(root, extra),
            "entries": entries,
            "nodes": nodes,
        }
        companion.parent.mkdir(parents=True, exist_ok=True)
        pending = companion.with_suffix(companion.suffix + ".tmp")
        pending.write_text(json.dumps(data, indent=2) + "\n")
        pending.replace(companion)
