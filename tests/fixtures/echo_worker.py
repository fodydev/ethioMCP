"""A test worker that uses the real protocol helper. Pass --bad-protocol to send a wrong hello."""

import importlib.util
import os
import sys

_proto_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "src",
    "ethiomcp",
    "core",
    "worker_protocol.py",
)
_spec = importlib.util.spec_from_file_location("worker_protocol", _proto_path)
proto = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(proto)
proto.protect_stdout()

if "--bad-protocol" in sys.argv:
    proto.PROTOCOL_VERSION = 999


def echo(**params):
    print("noise that must not reach the protocol stream")
    return params


def boom():
    raise ValueError("kaboom")


proto.serve({"echo": echo, "boom": boom})
