"""Command line: ethiomcp serve | setup | list | doctor."""

from __future__ import annotations

import argparse
import logging
import sys

from .core.connector import SetupContext
from .core.paths import data_dir
from .core.registry import discover, load_all


def _select(names: list[str]):
    available = discover()
    if not names:
        return [cls() for cls in available.values()]
    unknown = [n for n in names if n not in available]
    if unknown:
        sys.exit(f"unknown connector(s): {', '.join(unknown)}. Available: {', '.join(available)}")
    return [available[n]() for n in names]


def cmd_serve(args: argparse.Namespace) -> None:
    from .server import build_server

    kwargs = {}
    if args.transport != "stdio":
        kwargs = {"host": args.host, "port": args.port}
    mcp, connectors = build_server()
    try:
        mcp.run(transport=args.transport, **kwargs)
    finally:
        for c in connectors:
            c.close()


def cmd_setup(args: argparse.Namespace) -> None:
    options = dict(opt.split("=", 1) for opt in args.option)
    ctx = SetupContext(force=args.force, options=options)
    failed = []
    for c in _select(args.connectors):
        print(f"==> {c.name}: {c.title}")
        try:
            c.dir.mkdir(parents=True, exist_ok=True)
            c.setup(ctx)
            print(f"    {c.name} is {'ready' if c.is_ready() else 'NOT ready'}")
        except Exception as exc:
            failed.append(c.name)
            print(f"    setup failed: {exc}", file=sys.stderr)
    if failed:
        sys.exit(f"setup failed for: {', '.join(failed)}")


def cmd_list(args: argparse.Namespace) -> None:
    for c in load_all():
        mark = "✓" if c.is_ready() else "✗"
        print(f"{mark} {c.name:<16} {c.title}  [{c.license}]  {c.source_url}")


def cmd_doctor(args: argparse.Namespace) -> None:
    print(f"data dir: {data_dir()}")
    print(f"server python: {sys.version.split()[0]} ({sys.executable})")
    for c in _select(args.connectors):
        try:
            st = c.status()
        finally:
            c.close()
        mark = "✓" if st.ready else "✗"
        print(f"{mark} {c.name}: {st.detail}")
        for k, v in st.extra.items():
            if k != "hello":
                print(f"    {k}: {v}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ethiomcp", description="MCP server for Ethiopian linguistics"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("serve", help="run the MCP server")
    p.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("setup", help="download or install connector data")
    p.add_argument("connectors", nargs="*", help="connector names (default: all)")
    p.add_argument("--force", action="store_true", help="wipe and reinstall")
    p.add_argument(
        "-o",
        "--option",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="connector option, e.g. -o langs=am,ti",
    )
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("list", help="list connectors")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("doctor", help="check connector environments")
    p.add_argument("connectors", nargs="*")
    p.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    # Logs always go to stderr; stdout belongs to the MCP stdio transport.
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, stream=sys.stderr)
    args.func(args)


if __name__ == "__main__":
    main()
