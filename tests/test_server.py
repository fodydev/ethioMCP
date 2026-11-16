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


def test_afrim_tools_through_server(afrim):
    mcp, _ = build_server([afrim])
    out = _payload(_call(mcp, "afrim_transliterate", {"text": "selam bet"}))
    assert out["output"] == "ሰላም በት"
    assert out["words"][0]["in_wordlist"] == ["dictionary"]
    out = _payload(_call(mcp, "afrim_keystrokes", {"text": "ኢትዮጵያ"}))
    assert out["keys"] == "aityoPya"
    out = _payload(_call(mcp, "afrim_ethiopian_date", {"date": "16/11/2026"}))
    assert out["ethiopian"]["month_name"] == "ሕዳር" and out["ethiopian"]["year_geez"] == "፳፻፲፱"


def test_afrim_numerals_need_no_setup(data_dir):
    from ethiomcp.connectors.afrim_data import AfrimDataConnector

    mcp, _ = build_server([AfrimDataConnector()])
    assert _payload(_call(mcp, "afrim_geez_numeral", {"number": 1966}))["geez"] == "፲፱፻፷፮"
    with pytest.raises(Exception, match="ethiomcp setup afrim"):
        _call(mcp, "afrim_lookup", {"query": "ሰላም"})
