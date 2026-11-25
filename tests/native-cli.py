"""Wrapped native default builds must use prepared shared dependency artifacts."""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(subprocess.check_output(
    ["nix", "build", str(repo) + "#cli", "--no-link", "--print-out-paths"], text=True
).strip())
with tempfile.TemporaryDirectory(prefix="lake shared native ") as temporary:
    root = Path(temporary) / "project"
    shutil.copytree(repo / "tests/fixtures/native", root,
                    ignore=shutil.ignore_patterns(".lake", ".lake-purifier"))
    env = {**os.environ, "LAKE_PURIFIER_PROJECT": str(root)}
    subprocess.run([sdk / "bin/lake", "build"], cwd=root, env=env, check=True)
    assert (root / ".lake-purifier/environment-shared-profile").exists()
    library = root / ".lake/build/lib/libnativeProjectionProof_ffi.so"
    handle = ctypes.CDLL(str(library))
    handle.projection_initialize.restype = ctypes.c_int
    assert handle.projection_initialize() == 1
    handle.projection_answer.argtypes = [ctypes.c_uint32]
    handle.projection_answer.restype = ctypes.c_uint32
    for value in [*range(100), 0xffffffff]:
        assert handle.projection_answer(value) == (value + 41) % (1 << 32)
print("wrapped Lake default shared profile, real Batteries dependency and foreign export PASS")
