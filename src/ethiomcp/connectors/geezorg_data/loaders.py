"""Parsers for the geezorg/data archive. Each one produces plain dict entries.

Each dataset is described by a :class:`Dataset`, which records where its
files are and how to turn their rows into entries. To add a dataset, append it
to :data:`DATASETS`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ethiomcp.core import read_tsv, read_xlsx

ETHIOPIC = re.compile(r"[ሀ-᎟ⶀ-⷟꬀-꬯]")
GEMINATION_MARK = "፟"


def is_ethiopic(text: str) -> bool:
    return bool(ETHIOPIC.search(text))


def normalize(text: str) -> str:
    """Normalise for search: lowercase, drop the gemination mark and the Ethiopic wordspace."""
    return text.replace(GEMINATION_MARK, "").replace("፡", " ").strip().lower()


@dataclass
class Dataset:
    id: str
    kind: str  # "dictionary" | "verbs" | "places"
    language: str  # ISO code of the Ethiopic-script side
    description: str
    paths: list[str]  # relative to the repo root, glob patterns allowed
    parse: Callable[[Path], Iterator[dict[str, Any]]]

    def files(self, root: Path) -> list[Path]:
        out: list[Path] = []
        for pattern in self.paths:
            out.extend(sorted(p for p in root.glob(pattern) if p.is_file()))
        return out


# ---- parsers -------------------------------------------------------------
def parse_nmsu(path: Path) -> Iterator[dict[str, Any]]:
    """NMSU-Say: headword <TAB> pos <TAB> English gloss [<TAB> note]."""
    for row in read_tsv(path):
        if len(row) < 3 or not is_ethiopic(row[0]):
            continue
        yield {
            "headword": row[0],
            "pos": row[1],
            "gloss": row[2],
            "note": row[3] if len(row) > 3 else "",
        }


def parse_st_json(path: Path) -> Iterator[dict[str, Any]]:
    """Science & Technology dictionary: {"sciencedictionary": [{word, field, tr:{amh}}]}."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    items = data.get("sciencedictionary", []) if isinstance(data, dict) else data
    for item in items:
        amh = (item.get("tr") or {}).get("amh", "")
        if not amh:
            continue
        yield {
            "headword": amh,
            "gloss": item.get("word", ""),
            "field": item.get("field", ""),
        }


VERB_COLUMNS = [
    "simple_perfect",
    "compound_perfect",
    "contingent",
    "compound_imperfect",
    "jussive",
    "imperative",
    "gerund",
    "infinitive",
    "participle",
    "translation",
    "verb_type",
]


def parse_armbruster(path: Path) -> Iterator[dict[str, Any]]:
    for row in read_tsv(path):
        if not is_ethiopic(row[0]):
            continue
        entry = dict(zip(VERB_COLUMNS, row, strict=False))
        entry["headword"] = row[0]
        entry["gloss"] = entry.get("translation", "")
        yield entry


def parse_geonames(path: Path) -> Iterator[dict[str, Any]]:
    """Amharic name <TAB> FULL_NAME <TAB> FULL_NAME_ND. The Amharic column is often empty."""
    for row in read_tsv(path):
        if len(row) < 2:
            continue
        yield {
            "headword": row[0],
            "gloss": row[1],
            "name_nd": row[2] if len(row) > 2 else "",
        }


def xlsx_pairs(ethiopic_first: bool | None = None) -> Callable[[Path], Iterator[dict[str, Any]]]:
    """A generic parser for a two-language spreadsheet: it finds the Ethiopic
    column and the other text column in each row."""

    def parse(path: Path) -> Iterator[dict[str, Any]]:
        for row in read_xlsx(path):
            eth = [c for c in row if c and is_ethiopic(c)]
            other = [c for c in row if c and not is_ethiopic(c)]
            if not eth or not other:
                continue
            yield {"headword": eth[0], "gloss": " | ".join(other[:3]), "extra": eth[1:3]}

    return parse


def parse_kidane(path: Path) -> Iterator[dict[str, Any]]:
    """Kidane Wolde Kifle: Ge'ez headword | forms/etymology | Amharic definition (all Ethiopic)."""
    for row in read_xlsx(path):
        row = row + ["", "", ""]
        if not is_ethiopic(row[0]):
            continue
        yield {
            "headword": " ".join(row[0].split()),
            "forms": row[1],
            "definition_am": row[2],
            "gloss": row[2] or row[1],
        }


DATASETS: list[Dataset] = [
    Dataset(
        "nmsu-say",
        "dictionary",
        "am",
        "NMSU-Say Amharic-English dictionary (nouns, verbs, adjectives, adverbs) with POS",
        [
            "amharic/dictionaries/nmsu-say/*.csv",
            "amharic/dictionaries/nmsu-say/*.txt",
        ],
        parse_nmsu,
    ),
    Dataset(
        "science-technology",
        "dictionary",
        "am",
        "English-Amharic Science & Technology dictionary, with subject field codes",
        ["amharic/dictionaries/ST/*.json"],
        parse_st_json,
    ),
    Dataset(
        "armbruster-verbs",
        "verbs",
        "am",
        "Armbruster Amharic verb paradigms (perfect, imperfect, jussive, gerund, ...), "
        "with gemination marked (U+135F)",
        ["amharic/verbs/ArmbrusterVerbs-Geminated-*.txt"],
        parse_armbruster,
    ),
    Dataset(
        "geonames",
        "places",
        "am",
        "Ethiopian place names (Amharic and romanised)",
        ["amharic/toponymic/Amharic-GeoNames-*.txt"],
        parse_geonames,
    ),
    Dataset(
        "tigrinya-tuquabo-aressi",
        "dictionary",
        "ti",
        "Concise English-Tigrinya dictionary (Tuquabo Aressi)",
        ["tigrinya/**/ConciseEnglish-TigrinyaDictionary*.xlsx"],
        xlsx_pairs(),
    ),
    Dataset(
        "kidane-wolde-kifle",
        "dictionary",
        "gez",
        "Kidane Wolde Kifle Ge'ez-Amharic dictionary (headword, forms/etymology, "
        "Amharic definition)",
        ["geez/**/kidane-wolde-kifle-glosses.xlsx"],
        parse_kidane,
    ),
]


class Index:
    """Entries loaded into memory for each dataset, with simple ranked search."""

    def __init__(self, root: Path, cache_dir: Path) -> None:
        self.root = root
        self.cache_dir = cache_dir
        self._entries: dict[str, list[dict[str, Any]]] = {}

    def dataset(self, ds_id: str) -> Dataset:
        for ds in DATASETS:
            if ds.id == ds_id:
                return ds
        raise KeyError(ds_id)

    def entries(self, ds: Dataset) -> list[dict[str, Any]]:
        if ds.id not in self._entries:
            self._entries[ds.id] = self._load(ds)
        return self._entries[ds.id]

    def _load(self, ds: Dataset) -> list[dict[str, Any]]:
        # Spreadsheets are slow to parse, so cache the parsed entries as JSON.
        cache = self.cache_dir / f"{ds.id}.json"
        files = ds.files(self.root)
        if (
            cache.exists()
            and files
            and cache.stat().st_mtime >= max(f.stat().st_mtime for f in files)
        ):
            return json.loads(cache.read_text(encoding="utf-8"))
        out: list[dict[str, Any]] = []
        for f in files:
            rel = f.relative_to(self.root).as_posix()
            try:
                for entry in ds.parse(f):
                    entry["source"] = rel
                    out.append(entry)
            except Exception as exc:  # a malformed file must not break every lookup
                out.append({"headword": "", "gloss": "", "source": rel, "load_error": str(exc)})
        out = [e for e in out if e.get("headword") or e.get("gloss")]
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return out

    def search(
        self,
        query: str,
        *,
        kinds: tuple[str, ...] = ("dictionary",),
        language: str | None = None,
        datasets: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Rank matches: exact match first, then prefix, then word match, then substring.
        The headword is searched when the query is in Ethiopic script, otherwise the gloss."""
        q = normalize(query)
        if not q:
            return []
        field = "headword" if is_ethiopic(query) else "gloss"
        scored: list[tuple[int, int, dict[str, Any]]] = []
        for ds in DATASETS:
            if ds.kind not in kinds:
                continue
            if language and ds.language != language:
                continue
            if datasets and ds.id not in datasets:
                continue
            for e in self.entries(ds):
                text = normalize(str(e.get(field, "")))
                if not text or q not in text:
                    continue
                if text == q:
                    rank = 0
                elif text.startswith(q):
                    rank = 1
                elif re.search(rf"(^|[\s,;/(]){re.escape(q)}($|[\s,;/)])", text):
                    rank = 2
                else:
                    rank = 3
                scored.append((rank, len(text), {"dataset": ds.id, **e}))
        scored.sort(key=lambda t: (t[0], t[1]))
        return [e for _, _, e in scored[:limit]]
