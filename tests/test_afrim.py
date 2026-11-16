import os

import pytest

from ethiomcp.connectors.afrim_data import AfrimDataConnector, calendar
from ethiomcp.core import ConnectorError

pytestmark = pytest.mark.unit


def test_ready_only_after_setup(data_dir):
    assert not AfrimDataConnector().is_ready()


def test_config_includes_keymap_aliases_and_wordlists(afrim):
    am = afrim.scheme("am")
    assert am.keymap["ae"] == "አ" and am.keymap["aE"] == "አ"  # alias
    assert am.keymap["::"] == "።"  # included from ../gez/punctuation.toml
    assert am.keymap["yua"] == "ዟ"  # stray whitespace stripped
    assert am.datasets() == {"dictionary": 6, "names": 1}  # b.toml has no section header
    assert afrim.scheme("gez").words == []


def test_transliterate_longest_match(afrim):
    am = afrim.scheme("am")
    assert "".join(o for _, o in am.to_ethiopic("selam::")) == "ሰላም።"
    assert "".join(o for _, o in am.to_ethiopic("aityoPya")) == "ኢትዮጵያ"
    assert am.to_ethiopic("x") == [("x", "x")]


def test_keystrokes_round_trip(afrim):
    am = afrim.scheme("am")
    keys = "".join(k for _, k in am.to_keys("ኢትዮጵያ ቤት"))
    assert keys == "aityoPya biet"
    assert "".join(o for _, o in am.to_ethiopic(keys)) == "ኢትዮጵያ ቤት"


def test_search(afrim):
    am = afrim.scheme("am")
    assert [r["word"] for r in am.search("ኢትዮጵያ")] == ["ኢትዮጵያ", "ኢትዮጵያም"]
    assert am.search("AITYOPYA")[0]["key"] == "aityoPya"
    assert am.search("አበ", dataset="names") == [
        {"key": "aebebe", "word": "አበበ", "dataset": "names"}
    ]
    assert am.word("bet") == [["bet", "በት", "dictionary"]]


def test_cache_is_reused_and_rebuilt(afrim):
    afrim.scheme("am")
    cache = afrim.cache_dir / "am.json"
    assert cache.exists()

    names = afrim.repo / "am" / "names.toml"
    names.write_text(names.read_text(encoding="utf-8") + '"selam" = "ሰላም"\n', encoding="utf-8")
    st = cache.stat()
    os.utime(names, (st.st_atime, st.st_mtime + 10))
    assert AfrimDataConnector().scheme("am").datasets()["names"] == 2


def test_unknown_scheme(afrim):
    with pytest.raises(ConnectorError):
        afrim.scheme("xx")


@pytest.mark.parametrize(
    "number, geez",
    [
        (1, "፩"),
        (10, "፲"),
        (100, "፻"),
        (1966, "፲፱፻፷፮"),
        (2018, "፳፻፲፰"),
        (10000, "፼"),
        (12345, "፼፳፫፻፵፭"),
        (1000000, "፻፼"),
    ],
)
def test_geez_numeral(number, geez):
    assert calendar.geez_numeral(number) == geez


def test_geez_numeral_rejects_zero():
    with pytest.raises(ValueError):
        calendar.geez_numeral(0)


def test_gregorian_to_ethiopian():
    out = calendar.gregorian_to_ethiopian(*calendar.parse_date("24/07/26"))
    assert out["ethiopian"] == {"year": 2018, "month": 11, "day": 17, "month_name": "ሐምሌ"}
    assert out["formats"][:2] == ["17 ሐምሌ 2018", "ሐምሌ 17 ቀን 2018 ዓ.ም."]
    assert calendar.gregorian_to_ethiopian(2026, 9, 11)["ethiopian"]["day"] == 1  # new year


def test_ethiopian_to_gregorian_round_trip():
    out = calendar.ethiopian_to_gregorian(*calendar.parse_date("2019-03-07"))
    assert out["gregorian"] == {"year": 2026, "month": 11, "day": 16}
    assert calendar.ethiopian_to_gregorian(2019, 13, 6)["gregorian"]["month"] == 9  # leap Pagume
    with pytest.raises(ValueError):
        calendar.ethiopian_to_gregorian(2018, 13, 6)
