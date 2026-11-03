"""Exercise native dependency reuse, source edits, isolation and fallback."""

import hashlib
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
    / "bin"
)


def command(args, root, expected=0, **kwargs):
    result = subprocess.run(
        [str(x) for x in args], cwd=root, text=True, capture_output=True, **kwargs
    )
    assert result.returncode == expected, (
        args,
        result.returncode,
        result.stdout,
        result.stderr,
    )
    return result


with tempfile.TemporaryDirectory(prefix="lake-conformance-") as temporary:
    temporary = Path(temporary)
    root = temporary / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".lake", ".lake-purifier"),
    )
    env = dict(
        os.environ,
        LEAN_PATH=str(temporary / "poison"),
        LAKE_HOME=str(temporary / "wrong-lake"),
        RESERVOIR_API_URL="http://127.0.0.1:9",
    )
    command([cli / "lake", "build", "--verbose"], root, env=env)
    assert command([cli / "lake", "exe", "proof"], root, env=env).stdout.strip() == "42"
    command([cli / "lake", "--no-build", "build"], root, env=env)
    source = root / "PurifierProof.lean"
    original = source.read_text()
    assert "def answer : Nat := 42" in original
    source.write_text(
        original.replace("def answer : Nat := 42", "def answer : Nat := 43")
    )
    failed = subprocess.run(
        [cli / "lake", "build"], cwd=root, env=env, capture_output=True, text=True
    )
    assert failed.returncode != 0 and "answer = 42" in failed.stdout + failed.stderr, (
        failed
    )
    source.write_text(original)
    command([cli / "lake", "build"], root, env=env)
    assert command([cli / "lake", "exe", "proof"], root, env=env).stdout.strip() == "42"
    paths = command(
        [cli / "lake", "env", "lean", "--src-deps", "PurifierProof.lean"], root, env=env
    )
    assert "/nix/store/" in paths.stdout and "Aesop.lean" in paths.stdout, paths
    project = root / "lakefile.toml"
    saved = project.read_text()
    project.write_text(saved.replace('version = "0.1.0"', 'version = "0.2.0"'))
    rejected = subprocess.run(
        [cli / "lake", "build"], cwd=root, env=env, capture_output=True, text=True
    )
    assert rejected.returncode != 0 and "metadata changed" in rejected.stderr, rejected
    project.write_text(saved)
    subdir = root / "nested"
    subdir.mkdir()
    assert command([cli / "lake", "env", "pwd"], subdir, env=env).stdout.strip() == str(
        subdir
    )
    companion = temporary / "external.json"
    (root / "lake-purifier.lock.json").rename(companion)
    external = dict(
        env, LAKE_PURIFIER_PROJECT=str(root), LAKE_PURIFIER_LOCK=str(companion)
    )
    assert (
        command([cli / "lake", "exe", "proof"], subdir, env=external).stdout.strip()
        == "42"
    )
    command(["python3", repo / "tests/lsp.py", cli / "lake", root], root, env=external)
    profile = root / ".lake-purifier/environment-profile"
    assert profile.is_symlink()
    references = subprocess.check_output(
        ["nix-store", "--query", "--requisites", str(profile.resolve())], text=True
    )
    assert "lake-purifier-" in references and "purified-lake-aesop" in references, (
        references
    )
    # No lock delegates native I/O and status rather than replacing the tool.
    fallback = temporary / "fallback"
    fallback.mkdir()
    native = command(
        [
            cli / "lake",
            "env",
            "python3",
            "-c",
            "import sys; print(sys.stdin.read().strip()); print('native-stderr',file=sys.stderr); sys.exit(7)",
        ],
        fallback,
        expected=7,
        input="native-stdin\n",
    )
    assert (
        native.stdout.strip() == "native-stdin"
        and "native-stderr" in native.stderr
        and "impure" in native.stderr
    ), native
    bundle = command(
        [cli / "lake-purifier", "bundle", "--project", root, "--lock", companion], root
    )
    release = Path(bundle.stdout.strip().splitlines()[-1])
    archives = list(release.glob("*.tgz"))
    assert len(archives) == 1
    fake = temporary / "fake-gh"
    record = temporary / "publication.json"
    fake.write_text(
        "#!/usr/bin/env python3\nimport hashlib,json,os,pathlib,sys\np=pathlib.Path(sys.argv[4]);pathlib.Path(os.environ['PUBLICATION_RECORD']).write_text(json.dumps({'args':sys.argv[1:],'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))\n"
    )
    fake.chmod(0o755)
    publication = dict(
        os.environ, LAKE_PURIFIER_GH=str(fake), PUBLICATION_RECORD=str(record)
    )
    command(
        [
            cli / "lake-purifier",
            "publish",
            "--tag",
            "v0.1.0",
            "--project",
            root,
            "--lock",
            companion,
        ],
        root,
        env=publication,
    )
    uploaded = json.loads(record.read_text())
    assert uploaded["args"] == [
        "release",
        "upload",
        "v0.1.0",
        str(archives[0]),
        "--clobber",
    ]
    assert uploaded["sha256"] == hashlib.sha256(archives[0].read_bytes()).hexdigest()
    consumer = temporary / "consumer"
    shutil.copytree(
        repo / "examples/minimal",
        consumer,
        ignore=shutil.ignore_patterns(".lake", ".lake-purifier"),
    )
    command([cli / "lake", "unpack", archives[0]], consumer)
    command([cli / "lake", "--no-build", "build"], consumer)
    assert command([cli / "lake", "exe", "proof"], consumer).stdout.strip() == "42"

print("Native Lake dependency, working-tree, cache consumer and fallback proofs passed")
