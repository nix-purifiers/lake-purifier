import sys
import tempfile
from pathlib import Path
import json, os, select, subprocess, time

root = Path(sys.argv[2]).resolve()
fixture = root
source = fixture / "PurifierProof.lean"
env = os.environ.copy()
error = tempfile.TemporaryFile()
proc = subprocess.Popen(
    [sys.argv[1], "serve"],
    cwd=fixture,
    env=env,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=error,
    bufsize=0,
)
buffer = bytearray()


def send(message):
    blob = json.dumps(message).encode()
    proc.stdin.write(b"Content-Length: " + str(len(blob)).encode() + b"\r\n\r\n" + blob)
    proc.stdin.flush()


def read():
    deadline = time.monotonic() + 30
    while True:
        marker = buffer.find(b"\r\n\r\n")
        if marker >= 0:
            header = bytes(buffer[:marker])
            length = int(
                next(
                    line.split(b":", 1)[1].strip()
                    for line in header.split(b"\r\n")
                    if line.lower().startswith(b"content-length:")
                )
            )
            if len(buffer) >= marker + 4 + length:
                blob = bytes(buffer[marker + 4 : marker + 4 + length])
                del buffer[: marker + 4 + length]
                return json.loads(blob)
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([proc.stdout], [], [], remaining)[0]:
            raise TimeoutError("native Lean LSP response timeout")
        chunk = os.read(proc.stdout.fileno(), 65536)
        if not chunk:
            raise RuntimeError("native Lean LSP exited")
        buffer.extend(chunk)


try:
    send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": os.getpid(),
                "rootUri": fixture.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": fixture.as_uri(), "name": "proof"}],
            },
        }
    )
    while True:
        reply = read()
        if reply.get("id") == 1 and "method" not in reply:
            break
    assert "result" in reply, reply
    send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
    send(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": source.as_uri(),
                    "languageId": "lean4",
                    "version": 1,
                    "text": source.read_text(),
                }
            },
        }
    )
    send(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/definition",
            "params": {
                "textDocument": {"uri": source.as_uri()},
                "position": {"line": 0, "character": 10},
            },
        }
    )
    while True:
        reply = read()
        if reply.get("id") == 2 and "method" not in reply:
            break
        if "method" in reply and "id" in reply:
            result = (
                [None for _ in reply.get("params", {}).get("items", [])]
                if reply["method"] == "workspace/configuration"
                else None
            )
            send({"jsonrpc": "2.0", "id": reply["id"], "result": result})
    print(json.dumps(reply))
    assert "/nix/store/" in json.dumps(reply) and "Aesop.lean" in json.dumps(reply), (
        reply
    )
finally:
    try:
        send({"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": None})
        send({"jsonrpc": "2.0", "method": "exit", "params": None})
        proc.wait(timeout=5)
    except (BrokenPipeError, subprocess.TimeoutExpired):
        proc.kill()
        proc.wait()
    error.close()
