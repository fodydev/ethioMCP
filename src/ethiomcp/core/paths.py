"""Where connectors keep downloaded data.

Everything lives under one per-user cache directory, outside of the project:

- Linux:   ~/.cache/ethiomcp
- macOS:   ~/Library/Caches/ethiomcp
- Windows: %LOCALAPPDATA%\\ethiomcp\\Cache

Set ``ETHIOMCP_DATA_DIR`` to use another location.
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_cache_dir

ENV_DATA_DIR = "ETHIOMCP_DATA_DIR"


def data_dir() -> Path:
    override = os.environ.get(ENV_DATA_DIR)
    return Path(override).expanduser() if override else Path(user_cache_dir("ethiomcp"))


def connector_dir(name: str) -> Path:
    """Directory reserved for one connector (not created automatically)."""
    return data_dir() / name
