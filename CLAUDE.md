# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

ethioMCP is an MCP server that exposes Ethiopian/Eritrean linguistic resources as tools. Each upstream repository is a **connector**; see `docs/adding-a-connector.md` for the full guide.

## Commands

```bash
uv sync
uv run ruff format --check src tests && uv run ruff check src tests   # CI lint (line length 100, py310 target)
uv run pytest                                  # unit tests only (pytest.ini adds -m "not integration")
uv run pytest tests/test_afrim.py::test_search # single test
uv run pytest -m integration                   # real data; needs `ethiomcp setup` first
uv run ethiomcp setup [name] [-o key=value] [--force]   # fetch data / build venvs
uv run ethiomcp list | doctor [name] | serve [--transport streamable-http]
npx @modelcontextprotocol/inspector uv run ethiomcp serve
```

CI runs lint, then tests on Python 3.10–3.13, so keep 3.10-compatible code (e.g. `tomllib` needs the `tomli` fallback).

Set `ETHIOMCP_DATA_DIR` to keep experiments out of the real per-user cache (`~/.cache/ethiomcp`). `ETHIOMCP_CONNECTORS=a,b` restricts which connectors load.

## Architecture

- **Discovery** (`core/registry.py`): every sub-package of `ethiomcp.connectors` not starting with `_` is imported and its single `Connector` subclass registered; plugins can also come from the `ethiomcp.connectors` entry-point group. No core changes are needed to add a connector. `_template` and `_template_isolated` are copy-from starting points.
- **Connector contract** (`core/connector.py`): `setup(ctx)` (idempotent, writes only to `self.dir` = `<data dir>/<name>/`, CLI `-o` flags arrive in `ctx.options`), `is_ready()` (cheap check), `register(mcp)`. Tools are declared with `@self.tool(mcp)` inside `register`: the name becomes `<connector>_<fn name>`, the **docstring is the tool description the LLM reads**, sync functions run in a thread, `ConnectorError`/`ConnectorNotReady` become readable MCP tool errors, and readiness is enforced unless `needs_setup=False`. Every tool result spreads `**self.attribution` (connector, source, license).
- **Two kinds of connectors**:
  - In-process data connectors (`geezorg_data`, `afrim_data`): clone with `GitSource`, parse files, and cache parsed entries as JSON under `self.dir/index`, invalidated by source-file mtimes (parsing raw data can take a minute).
  - `IsolatedConnector` (`hornmorpho`): the library lives in its own uv-created venv with its own Python version (`core/envs.py`) and runs as a long-lived subprocess (`core/worker.py`) speaking JSON-lines. The server never imports it, which keeps GPL code and stray `print`s out of the server process. `worker_main.py` and `core/worker_protocol.py` run on the connector's interpreter, so they must be **stdlib-only with Python 3.8+ syntax**.
- `server.py` builds the `MCPServer` from loaded connectors and adds the `ethiomcp_connectors` tool; `cli.py` wraps it with `setup/list/doctor/serve`.

## Tests

- Unit tests use small copies of upstream data in `tests/fixtures/<name>_repo/` with fixtures in `tests/conftest.py` (`data_dir` points `ETHIOMCP_DATA_DIR` at a tmp dir). Git can't commit a nested `.git`, so fixtures that need one create the marker at runtime.
- Tests that need real data go in `tests/test_integration.py` with `@pytest.mark.integration` and skip when the connector isn't set up.
- `tests/test_server.py` calls tools end to end through `build_server(...)` + `mcp.call_tool`.
