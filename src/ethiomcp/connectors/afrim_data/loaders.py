"""Readers for afrim-data input-method configurations.

An afrim configuration is a TOML file. Its sections hold entries of three forms:

- ``"key" = "value"``
- ``"key" = { value = "...", alias = ["...", ...] }``
- ``"name" = { path = "./other.toml" }``, which includes another file

``[data]`` sections are the keyboard map (keystrokes -> characters).
``[translation]`` and ``[dictionary]`` sections are word lists (romanised word ->
word in Ge'ez script). ``[info]``, ``[core]`` and ``[translators]`` (Rhai
scripts, ported in :mod:`.calendar`) are not entries.

Parsing the full Amharic dictionary takes close to a minute, so a
:class:`Scheme` is cached as JSON and rebuilt only when a source file changes.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from ethiomcp.core import ConnectorError

ETHIOPIC = re.compile(r"[ሀ-᎟ⶀ-⷟꬀-꬯]")
NON_ENTRY_SECTIONS = {"info", "core", "translators"}
CACHE_VERSION = 1


def is_ethiopic(text: str) -> bool:
    return bool(ETHIOPIC.search(text))


@dataclass(frozen=True)
class SchemeInfo:
    id: str
    language: str
    description: str
    config: str  # main config file, relative to the repo root


# The Ethiopic-script input methods of afrim-data.
SCHEMES: dict[str, SchemeInfo] = {
    s.id: s
    for s in [
        SchemeInfo(
            "am",
            "am",
            "Amharic: keyboard map, Ge'ez punctuation, a ~340k-word Amharic wordlist "
            "and ~1.1k Ethiopian personal names",
            "am/am.toml",
        ),
        SchemeInfo("gez", "gez", "Ge'ez: keyboard map and Ge'ez punctuation", "gez/gez.toml"),
        SchemeInfo(
            "ethiopic",
            "mul",
            "Language-neutral Ethiopic keyboard map, including extended syllables",
            "ethiopic/ethiopic.toml",
        ),
        SchemeInfo(
            "geezime",
            "mul",
            "Keyboard map of EriLingual Solutions' GeezIME (https://geez-ime.vercel.app)",
            "geezime/geezime.toml",
        ),
    ]
}


class _Collector:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.keymap: dict[str, str] = {}
        self.primary: dict[str, str] = {}  # keymap without aliases
        self.words: list[list[str]] = []  # [key, value, dataset]
        self.files: list[str] = []

    def load(self, path: Path, *, kind: str | None, dataset: str | None) -> None:
        path = path.resolve()
        if self.root not in path.parents:
            raise ConnectorError(f"config includes a file outside the repository: {path}")
        self.files.append(path.relative_to(self.root).as_posix())
        with path.open("rb") as fh:
            doc = tomllib.load(fh)
        for name, value in doc.items():
            if name in NON_ENTRY_SECTIONS:
                continue
            if isinstance(value, dict) and _is_section(value):
                section_kind = "keymap" if name == "data" else "words"
                self._section(path, value, kind=kind or section_kind, dataset=dataset)
            else:
                # Some files have no section header: their entries are top-level.
                self._entry(path, name, value, kind=kind or "words", dataset=dataset or name)

    def _section(self, path: Path, section: dict, *, kind: str, dataset: str | None) -> None:
        for key, value in section.items():
            self._entry(path, key, value, kind=kind, dataset=dataset)

    def _entry(self, path: Path, key: str, value: Any, *, kind: str, dataset: str | None) -> None:
        if isinstance(value, dict) and "path" in value:
            self.load(path.parent / value["path"], kind=kind, dataset=dataset or key)
            return
        if isinstance(value, str):
            out, aliases = value, []
        elif isinstance(value, dict) and isinstance(value.get("value"), str):
            out, aliases = value["value"], list(value.get("alias", []))
        else:
            return
        out = out.strip()
        if not out:
            return
        if kind == "keymap":
            self.primary.setdefault(key, out)
            for k in [key, *aliases]:
                self.keymap.setdefault(k, out)
        else:
            self.words.append([key, out, dataset or ""])


def _is_section(table: dict) -> bool:
    """A section is a table of entries; an entry is a str, or a table with value/path."""
    return not ("value" in table or "path" in table)


class Scheme:
    """One input method: a keyboard map and, optionally, word lists."""

    def __init__(self, info: SchemeInfo, data: dict[str, Any]) -> None:
        self.info = info
        self.keymap: dict[str, str] = data["keymap"]
        self.primary: dict[str, str] = data["primary"]
        self.words: list[list[str]] = data["words"]
        self.files: list[str] = data["files"]
        self._max_key = max((len(k) for k in self.keymap), default=1)
        self._reverse: dict[str, str] | None = None
        self._by_key: dict[str, list[int]] | None = None
        self._by_lower: dict[str, list[int]] | None = None

    # ---- loading -------------------------------------------------------
    @classmethod
    def build(cls, root: Path, info: SchemeInfo) -> dict[str, Any]:
        config = root / info.config
        if not config.exists():
            raise ConnectorError(f"{info.config} not found in afrim-data")
        c = _Collector(root)
        c.load(config, kind=None, dataset=None)
        return {
            "version": CACHE_VERSION,
            "keymap": c.keymap,
            "primary": c.primary,
            "words": c.words,
            "files": c.files,
        }

    @classmethod
    def load(cls, root: Path, cache_dir: Path, info: SchemeInfo, *, force: bool = False):
        cache = cache_dir / f"{info.id}.json"
        if not force and cache.exists():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                mtime = cache.stat().st_mtime
                if data.get("version") == CACHE_VERSION and all(
                    (root / f).exists() and (root / f).stat().st_mtime <= mtime
                    for f in data["files"]
                ):
                    return cls(info, data)
            except (OSError, ValueError, KeyError):
                pass
        data = cls.build(root, info)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return cls(info, data)

    # ---- keyboard map --------------------------------------------------
    def to_ethiopic(self, text: str) -> list[tuple[str, str]]:
        """Greedy longest-match transliteration: a list of (keys, output) segments.
        Unmapped characters are returned unchanged, with keys == output."""
        out: list[tuple[str, str]] = []
        i = 0
        while i < len(text):
            for n in range(min(self._max_key, len(text) - i), 0, -1):
                chunk = text[i : i + n]
                if chunk in self.keymap:
                    out.append((chunk, self.keymap[chunk]))
                    i += n
                    break
            else:
                out.append((text[i], text[i]))
                i += 1
        return out

    @property
    def reverse(self) -> dict[str, str]:
        """Output -> the shortest primary key that types it."""
        if self._reverse is None:
            rev: dict[str, str] = {}
            for key, value in sorted(self.primary.items(), key=lambda kv: (len(kv[0]), kv[0])):
                rev.setdefault(value, key)
            self._reverse = rev
        return self._reverse

    def to_keys(self, text: str) -> list[tuple[str, str]]:
        """Ge'ez text -> a list of (character(s), keystrokes) segments."""
        rev = self.reverse
        longest = max((len(v) for v in rev), default=1)
        out: list[tuple[str, str]] = []
        i = 0
        while i < len(text):
            for n in range(min(longest, len(text) - i), 0, -1):
                chunk = text[i : i + n]
                if chunk in rev:
                    out.append((chunk, rev[chunk]))
                    i += n
                    break
            else:
                out.append((text[i], text[i]))
                i += 1
        return out

    # ---- word lists ----------------------------------------------------
    def _index(self) -> None:
        by_key: dict[str, list[int]] = {}
        by_lower: dict[str, list[int]] = {}
        for i, (key, _, _) in enumerate(self.words):
            by_key.setdefault(key, []).append(i)
            by_lower.setdefault(key.lower(), []).append(i)
        self._by_key, self._by_lower = by_key, by_lower

    def word(self, key: str) -> list[list[str]]:
        """Exact (case-sensitive) romanised-key lookup in the word lists."""
        if self._by_key is None:
            self._index()
        assert self._by_key is not None
        return [self.words[i] for i in self._by_key.get(key, [])]

    def search(self, query: str, *, dataset: str | None = None, limit: int = 20):
        """Rank: exact match, then case-insensitive match (Latin only), then prefix,
        then substring. Ge'ez-script queries search the words, Latin queries the keys."""
        query = query.strip()
        if not query:
            return []
        if self._by_key is None:
            self._index()
        ethiopic = is_ethiopic(query)
        q = query if ethiopic else query.lower()
        scored: list[tuple[int, int, int]] = []
        for i, (key, value, ds) in enumerate(self.words):
            if dataset and ds != dataset:
                continue
            if ethiopic:
                text = value
                if q not in text:
                    continue
                rank = 0 if text == q else 2 if text.startswith(q) else 3
            else:
                text = key.lower()
                if q not in text:
                    continue
                if key == query:
                    rank = 0
                elif text == q:
                    rank = 1
                else:
                    rank = 2 if text.startswith(q) else 3
            scored.append((rank, len(text), i))
        scored.sort()
        return [
            {"key": self.words[i][0], "word": self.words[i][1], "dataset": self.words[i][2]}
            for _, _, i in scored[:limit]
        ]

    def datasets(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for _, _, ds in self.words:
            counts[ds] = counts.get(ds, 0) + 1
        return counts
