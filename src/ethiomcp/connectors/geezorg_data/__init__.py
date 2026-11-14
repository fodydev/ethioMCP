"""geezorg/data connector: the GFF lexical archive for Amharic, Tigrinya and Ge'ez.

Upstream: https://github.com/geezorg/data (CC BY-SA 4.0). It is pure data, so it
runs in the server process.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ethiomcp.core import Connector, ConnectorError, GitSource, SetupContext, safe_join

from .loaders import DATASETS, Index, is_ethiopic, normalize

TEXT_SUFFIXES = {".txt", ".csv", ".tsv", ".json", ".tex", ".xml", ".md", ".html"}


class GeezorgDataConnector(Connector):
    name = "geezorg"
    title = "GFF Data Archive (geezorg/data)"
    description = (
        "Dictionaries (Amharic-English, Science & Technology, Tigrinya, Ge'ez), Amharic verb "
        "paradigms, place names and a POS-tagged Amharic corpus."
    )
    source_url = "https://github.com/geezorg/data"
    license = "CC BY-SA 4.0"

    source = GitSource(source_url)
    _index: Index | None = None

    @property
    def repo(self):
        return self.dir / "repo"

    def setup(self, ctx: SetupContext) -> None:
        self.source.ensure(self.repo, force=ctx.force, log=ctx.log)
        index = Index(self.repo, self.dir / "index")
        for ds in DATASETS:
            n = len(index.entries(ds))
            ctx.log(f"  indexed {ds.id}: {n} entries")

    def is_ready(self) -> bool:
        return (self.repo / ".git").exists()

    def index(self) -> Index:
        if self._index is None:
            self._index = Index(self.repo, self.dir / "index")
        return self._index

    def register(self, mcp: MCPServer) -> None:
        @self.tool(mcp)
        def list_datasets() -> dict[str, Any]:
            """List the structured datasets (dictionaries, verb paradigms, place names)
            that the geezorg tools search, with their language and source files."""
            return {
                "datasets": [
                    {
                        "id": ds.id,
                        "kind": ds.kind,
                        "language": ds.language,
                        "description": ds.description,
                        "files": [f.relative_to(self.repo).as_posix() for f in ds.files(self.repo)],
                    }
                    for ds in DATASETS
                ],
                **self.attribution,
            }

        @self.tool(mcp)
        def lookup(
            query: str, lang: str | None = None, dataset: str | None = None, limit: int = 20
        ) -> dict[str, Any]:
            """Look up a word in the dictionaries.

            A query in Ge'ez script (e.g. 'ቤት') searches headwords. A Latin-script
            query (e.g. 'house') searches the English glosses. Results are ranked
            exact match, then prefix, then whole word, then substring.
            lang: am | ti | gez filters by language. dataset: a dataset id from
            geezorg_list_datasets.
            """
            results = self.index().search(
                query,
                language=lang,
                datasets=[dataset] if dataset else None,
                limit=max(1, min(limit, 100)),
            )
            return {"query": query, "results": results, **self.attribution}

        @self.tool(mcp)
        def verb_paradigm(verb: str, limit: int = 5) -> dict[str, Any]:
            """Return the conjugation table of an Amharic verb from the Armbruster
            list: simple and compound perfect, contingent, imperfect, jussive,
            imperative, gerund, infinitive, participle, translation, verb type.
            Give the 3rd person masculine perfect in Ge'ez script (e.g. 'ሰበረ'),
            or an English translation (e.g. 'break'). Gemination is marked with U+135F."""
            results = self.index().search(verb, kinds=("verbs",), limit=max(1, min(limit, 50)))
            return {"query": verb, "results": results, **self.attribution}

        @self.tool(mcp)
        def place_names(query: str, limit: int = 20) -> dict[str, Any]:
            """Search Ethiopian place names, in Amharic script or in romanised form."""
            results = self.index().search(query, kinds=("places",), limit=max(1, min(limit, 100)))
            return {"query": query, "results": results, **self.attribution}

        @self.tool(mcp)
        def corpus_search(term: str, limit: int = 20, context: int = 60) -> dict[str, Any]:
            """Search the POS-tagged Walta Information Center (WIC) Amharic news corpus
            and return keyword-in-context lines. The tags are inside the text,
            e.g. '<word> <TAG>'. Use it to find real usage examples and
            part-of-speech tags."""
            files = sorted(self.repo.glob("amharic/tagged/WIC-Tagged-*/*UTF8*.txt"))
            if not files:
                raise ConnectorError("WIC tagged corpus not found in the repository")
            needle = normalize(term)
            hits: list[dict[str, Any]] = []
            for f in files:
                with f.open(encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, 1):
                        pos = normalize(line).find(needle)
                        if pos < 0:
                            continue
                        start = max(0, pos - context)
                        hits.append(
                            {
                                "source": f.relative_to(self.repo).as_posix(),
                                "line": lineno,
                                "kwic": line[start : pos + len(term) + context].strip(),
                            }
                        )
                        if len(hits) >= limit:
                            break
            return {"term": term, "hits": hits, **self.attribution}

        @self.tool(mcp)
        def browse(path: str = "") -> dict[str, Any]:
            """List the files and folders at a path of the archive, for example
            'amharic/dictionaries'. The archive also holds abbreviations, plurals,
            homonyms, gemination lists, parallel Amharic-English news and
            Sabaean/Falasi glossaries that have no dedicated tool."""
            target = safe_join(self.repo, path)
            if not target.is_dir():
                raise ConnectorError(f"not a directory: {path}")
            items = []
            for p in sorted(target.iterdir()):
                if p.name.startswith("."):
                    continue
                items.append(
                    {
                        "path": p.relative_to(self.repo).as_posix(),
                        "type": "dir" if p.is_dir() else "file",
                        "size": p.stat().st_size if p.is_file() else None,
                    }
                )
            return {"path": path, "items": items, **self.attribution}

        @self.tool(mcp)
        def read_file(path: str, offset: int = 0, limit: int = 200) -> dict[str, Any]:
            """Read lines [offset, offset+limit) of a text file in the archive
            (.txt/.csv/.json/.tex/.xml). Use geezorg_browse to find paths."""
            target = safe_join(self.repo, path)
            if not target.is_file():
                raise ConnectorError(f"no such file: {path}")
            if target.suffix.lower() not in TEXT_SUFFIXES:
                raise ConnectorError(
                    f"{target.suffix} files are not readable as text; "
                    "spreadsheets are searched through geezorg_lookup instead"
                )
            limit = max(1, min(limit, 1000))
            lines: list[str] = []
            total = 0
            with target.open(encoding="utf-8-sig", errors="replace") as fh:
                for i, line in enumerate(fh):
                    total = i + 1
                    if offset <= i < offset + limit:
                        lines.append(line.rstrip("\n"))
            return {
                "path": path,
                "offset": offset,
                "total_lines": total,
                "lines": lines,
                **self.attribution,
            }


__all__ = ["GeezorgDataConnector", "is_ethiopic"]
