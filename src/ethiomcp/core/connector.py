"""The connector contract.

A connector turns one external linguistic repository into MCP tools. To write
one, subclass :class:`Connector`, fill in the metadata, then implement:

- :meth:`Connector.setup`: fetch or install whatever the connector needs
  into ``self.dir``. It runs from ``ethiomcp setup <name>`` and must be safe to
  run again.
- :meth:`Connector.is_ready`: check cheaply that the setup has been done.
- :meth:`Connector.register`: add tools, resources and prompts to the server.

Inside ``register``, decorate tools with ``self.tool(mcp)``. It adds the
connector prefix to the tool name, and it turns "not set up yet" and other
errors into messages the LLM can read.
"""

from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .paths import connector_dir

log = logging.getLogger("ethiomcp")


class ConnectorNotReady(RuntimeError):
    """The data or environment a connector needs is missing."""


class ConnectorError(RuntimeError):
    """An error a tool reports to the LLM as a message, not a traceback."""


@dataclass
class Status:
    ready: bool
    detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SetupContext:
    """Options passed to :meth:`Connector.setup` from the CLI."""

    force: bool = False
    options: dict[str, str] = field(default_factory=dict)

    def log(self, message: str) -> None:
        print(message, flush=True)


class Connector:
    # Metadata. Subclasses must set ``name``; the rest is shown by `ethiomcp list`.
    name: ClassVar[str] = ""
    title: ClassVar[str] = ""
    description: ClassVar[str] = ""
    source_url: ClassVar[str] = ""
    license: ClassVar[str] = ""

    @property
    def dir(self) -> Path:
        return connector_dir(self.name)

    @property
    def attribution(self) -> dict[str, str]:
        return {"connector": self.name, "source": self.source_url, "license": self.license}

    # ---- lifecycle -----------------------------------------------------
    def setup(self, ctx: SetupContext) -> None:
        """Fetch or install the connector's data into ``self.dir``."""

    def is_ready(self) -> bool:
        return True

    def status(self) -> Status:
        if self.is_ready():
            return Status(True, "ready")
        return Status(False, f"not set up; run `ethiomcp setup {self.name}`")

    def require_ready(self) -> None:
        if not self.is_ready():
            raise ConnectorNotReady(
                f"The '{self.name}' connector is not set up on this server. "
                f"Ask the server administrator to run: ethiomcp setup {self.name}"
            )

    def register(self, mcp: MCPServer) -> None:
        raise NotImplementedError

    def close(self) -> None:
        """Release resources, such as worker processes, when the server stops."""

    # ---- helpers -------------------------------------------------------
    def tool(
        self, mcp: MCPServer, name: str | None = None, *, needs_setup: bool = True
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator: register ``fn`` as the MCP tool ``<connector>_<name>``.

        The function's signature and docstring become the tool schema and
        description. A :class:`ConnectorNotReady` or :class:`ConnectorError`
        raised inside it becomes an MCP tool error (``isError``) with a readable
        message. Synchronous functions run in a worker thread, so a slow
        connector call does not block the server.
        """

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = f"{self.name}_{name or fn.__name__}"
            is_async = inspect.iscoroutinefunction(fn)

            @functools.wraps(fn)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    if needs_setup:
                        self.require_ready()
                    if is_async:
                        return await fn(*args, **kwargs)
                    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))
                except (ConnectorNotReady, ConnectorError) as exc:
                    raise ToolError(f"[{self.name}] {exc}") from exc

            mcp.add_tool(wrapper, name=tool_name, description=inspect.getdoc(fn))
            return fn

        return decorator


class IsolatedConnector(Connector):
    """A connector whose library runs in its own virtualenv and Python version.

    Declare ``python`` (a version spec for uv, for example ``">=3.9,<3.13"``),
    ``requirements`` (pip requirement strings) and ``worker_script`` (a
    stdlib-only Python file that serves JSON-lines requests). Then call
    ``self.call(method, **params)`` from your tools.
    """

    python: ClassVar[str] = ">=3.9"
    requirements: ClassVar[list[str]] = []
    worker_script: ClassVar[Path | None] = None
    call_timeout: ClassVar[float] = 120.0

    _worker: Any = None

    @property
    def venv_dir(self) -> Path:
        return self.dir / "venv"

    def setup(self, ctx: SetupContext) -> None:
        from .envs import create_env

        create_env(self.venv_dir, self.python, self.requirements, force=ctx.force, log=ctx.log)
        self.post_install(ctx)

    def post_install(self, ctx: SetupContext) -> None:
        """Runs after the venv is ready, for example to download language data."""

    def is_ready(self) -> bool:
        from .envs import env_python

        return env_python(self.venv_dir).exists()

    def worker(self):
        from .worker import SubprocessWorker

        if self._worker is None:
            from .envs import env_python

            if self.worker_script is None:
                raise ConnectorError(f"{self.name}: no worker_script declared")
            self._worker = SubprocessWorker(
                [str(env_python(self.venv_dir)), "-u", str(self.worker_script)],
                name=self.name,
                timeout=self.call_timeout,
                env={"ETHIOMCP_CONNECTOR_DIR": str(self.dir)},
            )
        return self._worker

    def call(self, method: str, **params: Any) -> Any:
        self.require_ready()
        return self.worker().call(method, **params)

    def status(self) -> Status:
        base = super().status()
        if not base.ready:
            return base
        try:
            info = self.worker().hello()
        except Exception as exc:  # report every kind of failure in doctor
            return Status(False, f"worker failed: {exc}")
        return Status(True, "ready", info)

    def close(self) -> None:
        if self._worker is not None:
            self._worker.close()
            self._worker = None
