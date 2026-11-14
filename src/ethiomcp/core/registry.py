"""Connector discovery.

Connectors come from two places:

1. Built-in: every sub-package of ``ethiomcp.connectors`` whose name does not
   start with ``_``, and that defines exactly one :class:`Connector` subclass.
2. Plugins: entry points in the group ``ethiomcp.connectors`` that point at a
   Connector subclass. This lets ``pip install ethiomcp-foo`` add connectors.

``ETHIOMCP_CONNECTORS=a,b`` restricts which connectors are loaded.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import os
import pkgutil
from importlib.metadata import entry_points

from .connector import Connector, IsolatedConnector

log = logging.getLogger("ethiomcp")
ENTRY_POINT_GROUP = "ethiomcp.connectors"
ENV_ENABLED = "ETHIOMCP_CONNECTORS"


def _classes_in(module) -> list[type[Connector]]:
    return [
        obj
        for obj in vars(module).values()
        if inspect.isclass(obj)
        and issubclass(obj, Connector)
        and obj not in (Connector, IsolatedConnector)
        and obj.__module__ == module.__name__
        and obj.name
    ]


def discover() -> dict[str, type[Connector]]:
    found: dict[str, type[Connector]] = {}
    import ethiomcp.connectors as pkg

    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"{pkg.__name__}.{info.name}")
        except Exception:
            log.exception("failed to import connector %s", info.name)
            continue
        for cls in _classes_in(module):
            found[cls.name] = cls

    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            cls = ep.load()
        except Exception:
            log.exception("failed to load connector entry point %s", ep.name)
            continue
        if inspect.isclass(cls) and issubclass(cls, Connector) and cls.name:
            found[cls.name] = cls
    return dict(sorted(found.items()))


def enabled_names(available: dict[str, type[Connector]]) -> list[str]:
    raw = os.environ.get(ENV_ENABLED, "").strip()
    if not raw:
        return list(available)
    wanted = [n.strip() for n in raw.split(",") if n.strip()]
    unknown = [n for n in wanted if n not in available]
    if unknown:
        log.warning("unknown connectors in %s: %s", ENV_ENABLED, ", ".join(unknown))
    return [n for n in wanted if n in available]


def load_all() -> list[Connector]:
    available = discover()
    return [available[name]() for name in enabled_names(available)]
