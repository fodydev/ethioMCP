"""Server side of the worker protocol, for use inside a worker script.

STDLIB ONLY, Python 3.8+ syntax. This file runs on the connector's own
interpreter, not on the server's. A worker script loads it by path (see
``connectors/hornmorpho/worker_main.py``) and calls::

    serve({"analyze": analyze, ...})
"""

import json
import platform
import sys
import traceback

PROTOCOL_VERSION = 1


def protect_stdout():
    """Redirect print() to stderr so that library output cannot corrupt the protocol."""
    sys.stdout = sys.stderr


def serve(handlers, info=None):
    # Keep the real stdout for the protocol. Anything else the library prints goes to stderr.
    # (Call protect_stdout() before importing a noisy library.)
    out = sys.__stdout__
    sys.stdout = sys.stderr

    def send(obj):
        out.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        out.flush()

    hello = {
        "hello": PROTOCOL_VERSION,
        "python": platform.python_version(),
        "executable": sys.executable,
    }
    hello.update(info or {})
    send(hello)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req_id = None
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req["method"]
            if method not in handlers:
                raise KeyError("unknown method: " + method)
            result = handlers[method](**(req.get("params") or {}))
            send({"id": req_id, "result": result})
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            send({"id": req_id, "error": f"{type(exc).__name__}: {exc}"})
