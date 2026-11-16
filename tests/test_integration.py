"""Real-data tests. Run `uv run ethiomcp setup` first, then `uv run pytest -m integration`."""

import pytest

from ethiomcp.connectors.geezorg_data import GeezorgDataConnector
from ethiomcp.connectors.hornmorpho import HornMorphoConnector

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def hornmorpho():
    c = HornMorphoConnector()
    if not c.is_ready():
        pytest.skip("hornmorpho not set up")
    yield c
    c.close()


@pytest.fixture(scope="module")
def geezorg():
    c = GeezorgDataConnector()
    if not c.is_ready():
        pytest.skip("geezorg not set up")
    return c


@pytest.mark.slow
def test_hornmorpho_analyze(hornmorpho):
    result = hornmorpho.call("analyze", lang="a", word="የቤታችን")
    assert result[0]["lemma"] == "ቤት"
    assert "Case=Gen" in result[0]["udfeats"]


@pytest.mark.slow
def test_hornmorpho_generate_from_lemma(hornmorpho):
    out = hornmorpho.call("generate", lang="a", root="ሰበረ", pos="v")
    assert out["root"] == "ስብር"
    assert "ሰበረ" in out["words"]


def test_geezorg_real_lookups(geezorg):
    ix = geezorg.index()
    assert ix.search("abaxial")[0]["headword"] == "ቅጠል ጀርባ"
    assert ix.search("ሆነ", kinds=("verbs",))[0]["jussive"] == "ይሁን"


@pytest.fixture(scope="module")
def afrim():
    from ethiomcp.connectors.afrim_data import AfrimDataConnector

    c = AfrimDataConnector()
    if not c.is_ready():
        pytest.skip("afrim not set up")
    return c


def test_afrim_amharic_wordlist(afrim):
    am = afrim.scheme("am")
    assert am.word("selam")[0][1] == "ሰላም"
    assert am.search("ኢትዮጵያ", limit=1)[0]["key"] == "aityoPya"
    assert "".join(o for _, o in am.to_ethiopic("aityoPya")) == "ኢትዮጵያ"


def test_afrim_all_schemes_load(afrim):
    from ethiomcp.connectors.afrim_data.loaders import SCHEMES

    for scheme_id in SCHEMES:
        assert len(afrim.scheme(scheme_id).keymap) > 300
