import pytest

from ethiomcp.connectors.geezorg_data.loaders import is_ethiopic, normalize

pytestmark = pytest.mark.unit


def test_script_detection_and_normalisation():
    assert is_ethiopic("ቤት") and not is_ethiopic("house")
    assert normalize("ሰበ፟ረ") == "ሰበረ"
    assert normalize("የቤት፡እመቤት") == "የቤት እመቤት"


def test_ready_only_after_setup(data_dir):
    from ethiomcp.connectors.geezorg_data import GeezorgDataConnector

    assert not GeezorgDataConnector().is_ready()


def test_lookup_ethiopic_headword_exact_first(geezorg):
    results = geezorg.index().search("ቤት")
    assert results[0]["headword"] == "ቤት"
    assert results[0]["pos"] == "n"
    assert any(r["headword"] == "የቤት፡እመቤት" for r in results)


def test_lookup_english_gloss(geezorg):
    results = geezorg.index().search("two")
    assert [r["headword"] for r in results] == ["ሁለት"]


def test_verb_paradigm_ignores_gemination_mark(geezorg):
    (entry,) = geezorg.index().search("ሰበረ", kinds=("verbs",))
    assert entry["jussive"] == "ይሰበር"
    assert entry["translation"] == "break"
    (be,) = geezorg.index().search("be", kinds=("verbs",))
    assert be["infinitive"] == "መሆን"


def test_place_names(geezorg):
    (place,) = geezorg.index().search("አዳማ", kinds=("places",))
    assert place["name_nd"] == "Adama"


def test_language_filter(geezorg):
    assert geezorg.index().search("ቤት", language="ti") == []
