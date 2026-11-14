"""Builds the MCP server from the enabled connectors."""

from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer

from . import __version__
from .core.connector import Connector
from .core.registry import load_all

log = logging.getLogger("ethiomcp")

INSTRUCTIONS = """\
ethioMCP gives you tools for Ethiopian and Eritrean languages (Amharic, Tigrinya,
Oromo, Ge'ez, ...). Each tool name starts with the connector it comes from
(for example hornmorpho_*, geezorg_*). Prefer these tools over guessing for
morphology, segmentation, dictionary glosses and verb paradigms, and cite the
`source` and `license` fields returned with the results.
Call `ethiomcp_connectors` to see which connectors are available and ready."""


def build_server(connectors: list[Connector] | None = None) -> tuple[MCPServer, list[Connector]]:
    connectors = load_all() if connectors is None else connectors
    mcp = MCPServer("ethiomcp", instructions=INSTRUCTIONS, version=__version__)

    for c in connectors:
        try:
            c.register(mcp)
        except Exception:
            log.exception("connector %s failed to register", c.name)

    @mcp.tool(name="ethiomcp_connectors")
    def list_connectors() -> dict:
        """List the connectors on this server: what each one is, where its data
        comes from, its license, and whether it is ready to use."""
        return {
            "connectors": [
                {
                    "name": c.name,
                    "title": c.title,
                    "description": c.description,
                    "source": c.source_url,
                    "license": c.license,
                    "ready": c.is_ready(),
                }
                for c in connectors
            ]
        }

    return mcp, connectors
