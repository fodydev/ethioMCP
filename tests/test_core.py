import sys

import pytest

from ethiomcp.core import ConnectorError, safe_join
from ethiomcp.core.registry import discover, load_all
from ethiomcp.core.worker import SubprocessWorker

from .conftest import FIXTURES

pytestmark = pytest.mark.unit


def test_discover_builtin_connectors_and_skip_templates():
    found = discover()
    assert {"hornmorpho", "geezorg"} <= set(found)
    assert not any(name.startswith("template") for name in found)


def test_enable_list_filters_connectors(monkeypatch):
    monkeypatch.setenv("ETHIOMCP_CONNECTORS", "geezorg, nope")
    assert [c.name for c in load_all()] == ["geezorg"]


def test_safe_join_blocks_traversal(tmp_path):
    assert safe_join(tmp_path, "a/b") == (tmp_path / "a/b").resolve()
    with pytest.raises(ConnectorError):
        safe_join(tmp_path, "../etc/passwd")


def _worker(*extra):
    return SubprocessWorker(
        [sys.executable, str(FIXTURES / "echo_worker.py"), *extra], name="echo", timeout=10
    )


def test_worker_roundtrip_ignores_library_prints():
    w = _worker()
    try:
        assert w.call("echo", word="ሰላም", n=2) == {"word": "ሰላም", "n": 2}
        assert w.hello()["hello"] == 1
    finally:
        w.close()


def test_worker_errors_are_reported_and_worker_survives():
    w = _worker()
    try:
        with pytest.raises(ConnectorError, match="kaboom"):
            w.call("boom")
        with pytest.raises(ConnectorError, match="unknown method"):
            w.call("missing")
        assert w.call("echo", ok=True) == {"ok": True}
    finally:
        w.close()


def test_worker_restarts_after_close():
    w = _worker()
    w.call("echo")
    w.close()
    assert w.call("echo", again=1) == {"again": 1}
    w.close()


def test_worker_protocol_mismatch():
    w = _worker("--bad-protocol")
    with pytest.raises(ConnectorError, match="protocol mismatch"):
        w.call("echo")
