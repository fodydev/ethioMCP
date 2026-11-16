"""afrim-data connector: the Ethiopic input methods of the afrim IME.

Upstream: https://github.com/fodydev/afrim-data. It is pure TOML data, so it
runs in the server process. The Rhai translators (Ge'ez numerals, Ethiopian
dates) are ported to Python in :mod:`.calendar`.

``ethiomcp setup afrim -o path=/local/afrim-data`` uses a local clone instead
of cloning from GitHub.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ethiomcp.core import Connector, ConnectorError, GitSource, SetupContext

from . import calendar
from .loaders import SCHEMES, Scheme, is_ethiopic


class AfrimDataConnector(Connector):
    name = "afrim"
    title = "afrim-data (afrim input methods)"
    description = (
        "Romanised-keyboard <-> Ge'ez script transliteration (Amharic, Ge'ez, Ethiopic, "
        "GeezIME layouts), a ~340k-word Amharic spelling wordlist, Ethiopian names, "
        "Ge'ez numerals and Ethiopian calendar conversion."
    )
    source_url = "https://github.com/fodydev/afrim-data"
    license = "unspecified upstream (no LICENSE file)"

    source = GitSource(source_url)

    def __init__(self) -> None:
        self._schemes: dict[str, Scheme] = {}

    @property
    def repo(self) -> Path:
        return self.dir / "repo"

    @property
    def cache_dir(self) -> Path:
        return self.dir / "index"

    def setup(self, ctx: SetupContext) -> None:
        local = ctx.options.get("path")
        if local:
            src = Path(local).expanduser().resolve()
            if not (src / "am" / "am.toml").exists():
                raise ConnectorError(f"{src} does not look like an afrim-data checkout")
            if self.repo.is_symlink() or self.repo.exists():
                if not self.repo.is_symlink():
                    raise ConnectorError(f"{self.repo} exists and is not a link; use --force")
                self.repo.unlink()
            self.repo.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(src, self.repo, target_is_directory=True)
            ctx.log(f"Linked {self.repo} -> {src}")
        else:
            if self.repo.is_symlink():
                self.repo.unlink()
            self.source.ensure(self.repo, force=ctx.force, log=ctx.log)
        ctx.log("  indexing (parsing the Amharic wordlist takes a while)...")
        for info in SCHEMES.values():
            s = Scheme.load(self.repo, self.cache_dir, info, force=ctx.force)
            ctx.log(f"  indexed {info.id}: {len(s.keymap)} keys, {len(s.words)} words")

    def is_ready(self) -> bool:
        return (self.repo / "am" / "am.toml").exists()

    def scheme(self, scheme_id: str) -> Scheme:
        if scheme_id not in SCHEMES:
            raise ConnectorError(
                f"unknown scheme {scheme_id!r}; choose one of: {', '.join(SCHEMES)}"
            )
        if scheme_id not in self._schemes:
            self._schemes[scheme_id] = Scheme.load(self.repo, self.cache_dir, SCHEMES[scheme_id])
        return self._schemes[scheme_id]

    def register(self, mcp: MCPServer) -> None:
        @self.tool(mcp)
        def list_schemes() -> dict[str, Any]:
            """List the input-method schemes (keyboard layouts) with their language,
            number of keys and word lists. Scheme ids: am, gez, ethiopic, geezime."""
            out = []
            for info in SCHEMES.values():
                s = self.scheme(info.id)
                out.append(
                    {
                        "id": info.id,
                        "language": info.language,
                        "description": info.description,
                        "keys": len(s.keymap),
                        "wordlists": s.datasets(),
                        "files": s.files,
                    }
                )
            return {"schemes": out, **self.attribution}

        @self.tool(mcp)
        def transliterate(
            text: str, scheme: str = "am", use_wordlist: bool = True
        ) -> dict[str, Any]:
            """Convert romanised keyboard input to Ge'ez script, as the afrim input
            method types it (greedy longest key match). The 'am' layout is SERA-like
            and case-sensitive: consonant + e u i a ie o (ሰ=se ሱ=su ሲ=si ሳ=sa ሴ=sie
            ሶ=so), a bare consonant is the 6th form (ስ=s), capitals are other
            consonants (ጠ=Te ጨ=Ce ጰ=Pe ሸ=xe ቀ=qe), and a vowel standing alone takes
            an 'a' prefix (አ=ae ኢ=ai እ=a). Examples: 'selam' -> ሰላም,
            'aityoPya' -> ኢትዮጵያ, 'biet' -> ቤት. Punctuation: ':' -> ፡, '::' or '.' -> ።,
            ',' -> ፣. Use afrim_keystrokes to find the keys for a Ge'ez word.

            scheme: am (default) | gez | ethiopic | geezime.
            use_wordlist: with 'am', a word that is in the Amharic wordlist or the names
            list is replaced by its listed spelling (useful where the keyboard map is
            ambiguous). Each word reports whether it was found there.
            Returns the text and a per-word breakdown."""
            s = self.scheme(scheme)
            words = []
            out_parts: list[str] = []
            for token in re.split(r"(\s+)", text):
                if token.isspace() or not token:
                    out_parts.append(token)
                    continue
                segments = s.to_ethiopic(token)
                typed = "".join(o for _, o in segments)
                listed = s.word(token) if use_wordlist and s.words else []
                result = listed[0][1] if listed else typed
                out_parts.append(result)
                words.append(
                    {
                        "input": token,
                        "output": result,
                        "keymap_output": typed,
                        "in_wordlist": [w[2] for w in listed],
                        "segments": [[k, o] for k, o in segments],
                    }
                )
            return {
                "scheme": scheme,
                "input": text,
                "output": "".join(out_parts),
                "words": words,
                **self.attribution,
            }

        @self.tool(mcp)
        def keystrokes(text: str, scheme: str = "am") -> dict[str, Any]:
            """Give the keystrokes that type Ge'ez-script text with an afrim keyboard
            layout (the reverse of afrim_transliterate), e.g. ኢትዮጵያ -> 'aityoPya'.
            Each character uses the shortest key sequence. Returns the keystroke
            string and a per-character breakdown. scheme: am | gez | ethiopic | geezime."""
            s = self.scheme(scheme)
            segments = s.to_keys(text)
            return {
                "scheme": scheme,
                "input": text,
                "keys": "".join(k for _, k in segments),
                "segments": [[c, k] for c, k in segments],
                "unmapped": sorted({c for c, k in segments if c == k and is_ethiopic(c)}),
                **self.attribution,
            }

        @self.tool(mcp)
        def lookup(query: str, dataset: str | None = None, limit: int = 20) -> dict[str, Any]:
            """Search the Amharic wordlist (~340k inflected word forms crawled from
            the web) and the Ethiopian personal-names list. Use it to check that an
            Amharic word exists and how it is spelled; there are no glosses.
            A Ge'ez-script query (e.g. 'ኢትዮጵያ') searches the words; a romanised
            query (e.g. 'aityoPya') searches the keyboard spellings. Ranking:
            exact, case-insensitive (romanised only), prefix, then substring.
            dataset: 'dictionary' or 'names' to restrict the search."""
            results = self.scheme("am").search(
                query, dataset=dataset, limit=max(1, min(limit, 200))
            )
            return {"query": query, "results": results, **self.attribution}

        @self.tool(mcp, needs_setup=False)
        def geez_numeral(number: int) -> dict[str, Any]:
            """Write a positive integer (up to 13 digits) with Ge'ez numerals,
            e.g. 1966 -> ፲፱፻፷፮, 10000 -> ፼, 2018 -> ፳፻፲፰."""
            try:
                return {"number": number, "geez": calendar.geez_numeral(number), **self.attribution}
            except ValueError as exc:
                raise ConnectorError(str(exc)) from exc

        @self.tool(mcp, needs_setup=False)
        def ethiopian_date(date: str, calendar_of_input: str = "gregorian") -> dict[str, Any]:
            """Convert a date between the Gregorian and the Ethiopian calendar.
            date: DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY (2-digit years are 20YY) or
            YYYY-MM-DD. calendar_of_input: 'gregorian' (default) or 'ethiopian'.
            Returns both dates, the Ethiopian month name, the year in Ge'ez numerals,
            and formatted strings such as '6 ሕዳር 2019' and 'ሕዳር 6 ቀን 2019 ዓ.ም.'."""
            try:
                y, m, d = calendar.parse_date(date)
                if calendar_of_input == "gregorian":
                    out = calendar.gregorian_to_ethiopian(y, m, d)
                elif calendar_of_input == "ethiopian":
                    out = calendar.ethiopian_to_gregorian(y, m, d)
                else:
                    raise ValueError("calendar_of_input must be 'gregorian' or 'ethiopian'")
                out["ethiopian"]["year_geez"] = calendar.geez_numeral(out["ethiopian"]["year"])
            except ValueError as exc:
                raise ConnectorError(str(exc)) from exc
            return {"input": date, **out, **self.attribution}


__all__ = ["AfrimDataConnector"]
