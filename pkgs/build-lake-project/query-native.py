"""Retain actual native query results for caller-authored standalone targets."""
import json
from pathlib import Path
import subprocess
import sys

lake, overrides, spec, destination = sys.argv[1:]
records = {}
for name, product in json.loads(Path(spec).read_text()).items():
    if "target" not in product:
        continue
    command = [lake, "--packages=" + overrides, "--json", "query", product["target"]]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    path = json.loads(result.stdout)
    if not isinstance(path, str):
        raise ValueError("native target query did not return an artifact path")
    records[name] = {"command": command, "stdout": result.stdout, "path": path}
Path(destination).write_text(json.dumps(records, sort_keys=True) + "\n")
