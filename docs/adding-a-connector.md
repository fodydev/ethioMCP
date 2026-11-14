# Adding a connector

A **connector** turns one external linguistic repository into MCP tools. Each
connector is a folder in `src/ethiomcp/connectors/`, and the server finds it
automatically. You don't need to change anything in the core.

## 1. Choose a template

| Your repository is… | Copy | Runs |
|---|---|---|
| Data: TSV, CSV, JSON, XLSX, text corpora, wordlists | `connectors/_template` | inside the server |
| A Python library: analyzers, taggers, models | `connectors/_template_isolated` | in its own venv and Python version, as a separate process |

```bash
cp -r src/ethiomcp/connectors/_template src/ethiomcp/connectors/my_lexicon
```

Folders whose names start with `_` are ignored by discovery. Your folder name
must not start with `_`.

## 2. Fill in the metadata

```python
class MyLexiconConnector(Connector):
    name = "mylex"                 # tool prefix -> mylex_lookup, mylex_...
    title = "My Lexicon"
    description = "Oromo-English lexicon with ..."   # the LLM reads this
    source_url = "https://github.com/owner/repo"
    license = "CC BY 4.0"          # returned with every result for attribution
```

## 3. Fetch the data in `setup`

`setup` runs from `ethiomcp setup mylex`. It must be safe to run more than
once. Write everything to `self.dir`, which is `<cache>/mylex/`.

```python
source = GitSource("https://github.com/owner/repo")       # shallow clone, then pull

def setup(self, ctx):
    self.source.ensure(self.dir / "repo", force=ctx.force, log=ctx.log)

def is_ready(self):
    return (self.dir / "repo" / ".git").exists()
```

`ctx.options` holds the `-o key=value` flags from the CLI, for example
`ethiomcp setup hornmorpho -o langs=am,ti`.

## 4. Write the tools in `register`

```python
def register(self, mcp):
    @self.tool(mcp)
    def lookup(word: str, limit: int = 20) -> dict:
        """Look up an Oromo word. Input in Latin script (Qubee). Returns glosses and POS."""
        ...
        return {"results": hits, **self.attribution}
```

`self.tool(mcp)` does the following for you:
- Names the tool `<connector>_<function name>`.
- Builds the tool schema from the type hints, and uses the **docstring** as the
  tool description. Write the docstring for the LLM: give the input script,
  language codes and examples.
- Rejects the call with "run `ethiomcp setup mylex`" if `is_ready()` is false.
  Pass `needs_setup=False` for tools that don't need data.
- Turns `ConnectorError("...")` into a readable MCP tool error.
- Runs synchronous functions in a thread, so slow work doesn't block the server.

Useful helpers in `ethiomcp.core`:
- `read_tsv(path)`
- `read_xlsx(path)`
- `safe_join(root, user_path)`, which blocks path traversal
- `GitSource`

## 5. Isolated connectors (Python libraries)

```python
class MyTaggerConnector(IsolatedConnector):
    name = "mytagger"
    python = ">=3.9,<3.12"                    # any spec uv understands
    requirements = ["mytagger==2.0"]          # or "pkg @ git+https://..." / a wheel URL
    worker_script = Path(__file__).with_name("worker_main.py")

    def post_install(self, ctx):              # optional: download models
        run_in_env(self.venv_dir, "import mytagger; mytagger.download()", log=ctx.log)

    def register(self, mcp):
        @self.tool(mcp)
        def tag(sentence: str) -> dict:
            """..."""
            return {"tags": self.call("tag", sentence=sentence), **self.attribution}
```

`worker_main.py` runs on the **connector's** interpreter. Keep it to the
standard library plus your library, with Python 3.8+ syntax. Call
`proto.protect_stdout()` before you import a library that prints. Return only
JSON-serialisable values.

Why it is built this way:
- The library's Python version and dependencies can't conflict with the server
  or with other connectors.
- GPL libraries stay in a separate process.
- Stray `print`s can't corrupt the MCP stdio stream.
- The worker stays alive between calls, so models load only once.

## 6. Check it

```bash
uv run ethiomcp setup mylex
uv run ethiomcp doctor mylex          # ready? which interpreter?
uv run ethiomcp list
npx @modelcontextprotocol/inspector uv run ethiomcp serve
```

Add unit tests against a small fixture copy of the data in `tests/fixtures/`,
and mark real-data tests with `@pytest.mark.integration`.

## Connectors from another package

A separate pip package can provide connectors through an entry point. The
server's code stays unchanged:

```toml
[project.entry-points."ethiomcp.connectors"]
mylex = "ethiomcp_mylex:MyLexiconConnector"
```
