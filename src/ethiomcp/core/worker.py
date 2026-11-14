"""JSON-lines RPC with a long-lived child Python process.

Protocol (one JSON object per line):

- On startup the child writes ``{"hello": <protocol>, "python": "<version>", ...}``.
- The server sends ``{"id": n, "method": "...", "params": {...}}``.
- The child answers ``{"id": n, "result": ...}`` or ``{"id": n, "error": "..."}``.

The child's stdout carries the protocol only. Logs and anything the library
prints must go to stderr; the worker scripts redirect ``sys.stdout``.
``worker_protocol.py`` holds a stdlib-only helper that worker scripts can copy
or import.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from typing import Any

from .connector import ConnectorError

PROTOCOL_VERSION = 1


class SubprocessWorker:
    def __init__(
        self,
        cmd: list[str],
        *,
        name: str,
        timeout: float = 120.0,
        startup_timeout: float = 300.0,
        env: dict[str, str] | None = None,
    ) -> None:
        self.cmd = cmd
        self.name = name
        self.timeout = timeout
        self.startup_timeout = startup_timeout
        self.env = env or {}
        self._proc: subprocess.Popen[str] | None = None
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._next_id = 0
        self._hello: dict[str, Any] = {}

    # ---- process management -------------------------------------------
    def _start(self) -> None:
        self._lines = queue.Queue()
        self._proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,  # the worker's logs go to the server's stderr, never to MCP stdout
            text=True,
            encoding="utf-8",
            bufsize=1,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", **self.env},
        )
        proc = self._proc

        def pump() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                self._lines.put(line)
            self._lines.put(None)

        threading.Thread(target=pump, daemon=True, name=f"{self.name}-worker").start()
        hello = self._read(self.startup_timeout)
        if hello.get("hello") != PROTOCOL_VERSION:
            self.close()
            raise ConnectorError(
                f"{self.name}: worker protocol mismatch (got {hello.get('hello')!r}, "
                f"expected {PROTOCOL_VERSION}); re-run `ethiomcp setup {self.name}`"
            )
        self._hello = hello

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _read(self, timeout: float) -> dict[str, Any]:
        while True:
            try:
                line = self._lines.get(timeout=timeout)
            except queue.Empty:
                self.close()
                raise ConnectorError(
                    f"{self.name}: worker timed out after {timeout:.0f}s"
                ) from None
            if line is None:
                code = self._proc.poll() if self._proc else None
                self._proc = None
                raise ConnectorError(f"{self.name}: worker exited (code {code}); see server logs")
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                # Stray output from the library: send it to the log and keep reading.
                print(f"[{self.name}] {line}", file=sys.stderr)

    def hello(self) -> dict[str, Any]:
        with self._lock:
            if not self._alive():
                self._start()
            return dict(self._hello)

    def call(self, method: str, **params: Any) -> Any:
        with self._lock:
            if not self._alive():
                self._start()
            assert self._proc is not None and self._proc.stdin is not None
            self._next_id += 1
            req_id = self._next_id
            self._proc.stdin.write(
                json.dumps({"id": req_id, "method": method, "params": params}, ensure_ascii=False)
                + "\n"
            )
            self._proc.stdin.flush()
            while True:
                msg = self._read(self.timeout)
                if msg.get("id") == req_id:
                    break
            if "error" in msg:
                raise ConnectorError(f"{self.name}.{method}: {msg['error']}")
            return msg.get("result")

    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
