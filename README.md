<div align="center">
  <h1><code>ethioMCP</code></h1>
  <p><strong>An MCP server that extends LLMs such as Claude and ChatGPT with Ethiopian linguistic resources.</strong></p>
  <p>
    <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="python">
    <img src="https://img.shields.io/badge/MCP-2.x-purple" alt="mcp">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="license">
  </p>
</div>

## About

LLMs are weak at the morphology and lexicon of Ethiopian and Eritrean languages.
ethioMCP gives them tools backed by established linguistic repositories. Each
repository is a **connector**, and adding a new one is a single folder (see
[docs/adding-a-connector.md](docs/adding-a-connector.md)).

## Connectors

### `hornmorpho`: [hltdi/HornMorpho](https://github.com/hltdi/HornMorpho)

License: GPL-3.0. It runs as a separate process.

| Tool | What it does |
|---|---|
| `hornmorpho_analyze` | Analyzes a word: lemma, root, POS, segmentation, UD features, UniMorph tags, transliteration, morphemes |
| `hornmorpho_analyze_sentence` | Analyzes a tokenized sentence and returns CoNLL-U |
| `hornmorpho_generate` | Generates word forms from a root (`ስብር`) or a lemma (`ሰበረ`), with features |
| `hornmorpho_phonetic` | Transliteration that shows gemination and epenthetic vowels |
| `hornmorpho_languages` | Supported languages: `am`, `ti`, `om`, `tig` |

### `geezorg`: [geezorg/data](https://github.com/geezorg/data)

License: CC BY-SA 4.0.

| Tool | What it does |
|---|---|
| `geezorg_lookup` | Dictionary search in either direction: Amharic (NMSU-Say, Science & Technology), Tigrinya and Ge'ez (Kidane Wolde Kifle) |
| `geezorg_verb_paradigm` | Armbruster Amharic verb tables: perfect, imperfect, jussive, gerund, and the other forms |
| `geezorg_place_names` | Ethiopian toponyms |
| `geezorg_corpus_search` | Keyword-in-context search of the POS-tagged WIC Amharic news corpus |
| `geezorg_list_datasets`, `geezorg_browse`, `geezorg_read_file` | Explore the rest of the archive |

`ethiomcp_connectors` lists the connectors and whether each one is ready.

## Install

```bash
git clone <this repo> && cd ethioMCP
uv sync
uv run ethiomcp setup                      # all connectors (HornMorpho: am,ti,om)
uv run ethiomcp setup hornmorpho -o langs=am
uv run ethiomcp doctor
```

Downloaded data goes to a per-user cache directory, not to the project:
`~/.cache/ethiomcp` on Linux, `~/Library/Caches/ethiomcp` on macOS, and
`%LOCALAPPDATA%\ethiomcp\Cache` on Windows. Set `ETHIOMCP_DATA_DIR` to use
another location.

Connectors that need their own Python environment get a venv inside that
folder, with the Python version they declare. For example, HornMorpho runs on
Python < 3.13, whatever version the server uses. `uv` downloads the
interpreter if needed.

## Use it

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ethiomcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/ethioMCP", "run", "ethiomcp", "serve"]
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add ethiomcp -- uv --directory /path/to/ethioMCP run ethiomcp serve
```

**ChatGPT** (developer mode or custom connectors) needs an HTTP endpoint:

```bash
uv run ethiomcp serve --transport streamable-http --host 0.0.0.0 --port 8000
# expose https://<host>/mcp, e.g. with a reverse proxy or tunnel
```

To enable only some connectors: `ETHIOMCP_CONNECTORS=geezorg uv run ethiomcp serve`.

> The first HornMorpho call in a session loads the language model (~20–60 s).
> Later calls are fast, because the worker stays alive.

## Development

```bash
uv run ruff check && uv run ruff format --check
uv run pytest                    # unit tests, no network
uv run pytest -m integration     # real data (run `ethiomcp setup` first)
npx @modelcontextprotocol/inspector uv run ethiomcp serve
```

## License

The ethioMCP code is MIT. Each connector's data and libraries keep their
upstream license, which is reported with every tool result. HornMorpho (GPL-3.0)
is never imported into the server process.
