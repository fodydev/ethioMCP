"""TEMPLATE: an in-process connector over a data repository.

To use it:
1. Copy this folder to ``connectors/<your_name>/``. The folder name must not
   start with ``_``, because folders starting with ``_`` are skipped by
   discovery.
2. Rename the class and fill in the metadata.
3. Point ``source`` at the repository and write your tools in ``register``.
4. Run ``uv run ethiomcp setup <name>``, then ``uv run ethiomcp list``.

Use this template when the repository is data: text, CSV, JSON, XLSX, or code
that works with the server's own dependencies. If you have to import a library
that has its own requirements or Python version, use ``_template_isolated``.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ethiomcp.core import Connector, ConnectorError, GitSource, SetupContext, read_tsv, safe_join


class TemplateConnector(Connector):
    name = "template"  # tool prefix: template_*
    title = "Template connector"
    description = "One sentence the LLM reads to decide when to use this connector."
    source_url = "https://github.com/OWNER/REPO"
    license = "CC BY 4.0"  # the upstream license; it is returned with every result

    source = GitSource(source_url)

    @property
    def repo(self):
        return self.dir / "repo"

    def setup(self, ctx: SetupContext) -> None:
        self.source.ensure(self.repo, force=ctx.force, log=ctx.log)

    def is_ready(self) -> bool:
        return (self.repo / ".git").exists()

    def register(self, mcp: MCPServer) -> None:
        @self.tool(mcp)
        def lookup(word: str, limit: int = 20) -> dict[str, Any]:
            """Docstring = tool description shown to the LLM. Say what it does,
            what input format it expects (script, language codes) and what it returns."""
            path = safe_join(self.repo, "wordlist.tsv")
            if not path.exists():
                raise ConnectorError("wordlist.tsv not found")  # becomes an MCP tool error
            hits = [row for row in read_tsv(path) if row and row[0] == word][:limit]
            return {"query": word, "results": hits, **self.attribution}
