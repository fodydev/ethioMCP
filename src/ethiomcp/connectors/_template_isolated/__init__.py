"""TEMPLATE: an isolated connector over a Python library.

The library is installed into ``<cache>/<name>/venv``, using the Python version
declared in ``python``. It runs in a separate process, so its Python version,
its dependencies, its license and anything it prints cannot affect the server.

To use it:
1. Copy this folder to ``connectors/<your_name>/``. The name must not start
   with ``_``.
2. Fill in the metadata, ``python`` and ``requirements``.
3. Write the library calls in ``worker_main.py``. It must use only the
   standard library plus your library, and Python 3.8+ syntax.
4. Expose them as tools in ``register`` with ``self.call("method", **params)``.
5. Run ``uv run ethiomcp setup <name>``, then ``uv run ethiomcp doctor <name>``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ethiomcp.core import IsolatedConnector, SetupContext


class TemplateIsolatedConnector(IsolatedConnector):
    name = "template_isolated"
    title = "Template isolated connector"
    description = "One sentence the LLM reads to decide when to use this connector."
    source_url = "https://github.com/OWNER/REPO"
    license = "GPL-3.0 (runs as a separate process)"

    python = ">=3.9,<3.13"  # any version spec uv understands
    requirements = ["somelib==1.2.3"]  # or "pkg @ git+https://..." / a wheel URL
    worker_script = Path(__file__).with_name("worker_main.py")
    call_timeout = 120.0

    def post_install(self, ctx: SetupContext) -> None:
        """Optional: download models or data once the library is installed, e.g.
        ``run_in_env(self.venv_dir, "import somelib; somelib.download()", log=ctx.log)``."""

    def register(self, mcp: MCPServer) -> None:
        @self.tool(mcp)
        def analyze(text: str) -> dict[str, Any]:
            """Docstring = tool description shown to the LLM."""
            return {"result": self.call("analyze", text=text), **self.attribution}
