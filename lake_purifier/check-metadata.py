import json
import sys

with open(sys.argv[1]) as expected, open(sys.argv[2]) as actual:
    if json.load(expected) != json.load(actual):
        raise SystemExit("Native Lake package metadata differs from its lock")
