import json

import anyio
import pytest

from ethiomcp.connectors.geezorg_data import GeezorgDataConnector
from ethiomcp.connectors.hornmorpho import HornMorphoConnector
from ethiomcp.server import build_server

pytestmark = pytest.mark.unit


def _call(mcp, name, args):
    async def go():
        return await mcp.call_tool(name, args)

    return anyio.run(go)


def _payload(result):
    content = result[0] if isinstance(result, tuple) else result
    content = getattr(content, "content", content)
    return json.loads(content[0].text)


def test_tools_are_prefixed_and_listed(data_dir):
    mcp, _ = build_server([GeezorgDataConnector(), HornMorphoConnector()])

    async def names():
        return {t.name for t in await mcp.list_tools()}

    tools = anyio.run(names)
    assert {"geezorg_lookup", "hornmorpho_analyze", "ethiomcp_connectors"} <= tools


def test_not_ready_connector_returns_setup_hint(data_dir):
    mcp, _ = build_server([HornMorphoConnector()])
    with pytest.raises(Exception, match="ethiomcp setup hornmorpho"):
        _call(mcp, "hornmorpho_analyze", {"word": "ቤት"})


def test_setup_free_tool_works_without_setup(data_dir):
    mcp, _ = build_server([HornMorphoConnector()])
    langs = _payload(_call(mcp, "hornmorpho_languages", {}))
    assert {"code": "am", "name": "Amharic"} in langs["languages"]


def test_geezorg_lookup_through_server(geezorg):
    mcp, _ = build_server([geezorg])
    out = _payload(_call(mcp, "geezorg_lookup", {"query": "abaxial"}))
    assert out["results"][0]["headword"] == "ቅጠል ጀርባ"
    assert out["license"] == "CC BY-SA 4.0"
