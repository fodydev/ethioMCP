"""TEMPLATE worker. It runs inside the connector's venv, not in the server.

STDLIB + your library ONLY, Python 3.8+ syntax.
"""

import importlib.util
import os

_proto_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "core", "worker_protocol.py"
)
_spec = importlib.util.spec_from_file_location("worker_protocol", _proto_path)
proto = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(proto)

proto.protect_stdout()  # call this BEFORE importing a library that prints


def analyze(text):
    import somelib  # import lazily, so the startup handshake stays fast

    return somelib.analyze(text)  # return only JSON-serialisable values


if __name__ == "__main__":
    proto.serve({"analyze": analyze})
