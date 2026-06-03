"""Entry point for ``python -m hass_client.sandbox_v2``.

The Sandbox v2 manager spawns this module as a subprocess. CLI arguments
mirror what the websocket client will need in Phase 4 so the manager-side
command line is stable across phases.
"""

import argparse
import asyncio
import logging
import sys

from hass_client.sandbox import SandboxRuntime


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hass_client.sandbox_v2",
        description="Sandbox v2 runtime process.",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Sandbox name, e.g. built-in / custom / main",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Websocket URL of the main Home Assistant instance.",
    )
    parser.add_argument(
        "--token",
        required=True,
        help="Scoped sandbox access token for authenticating with main.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level for the runtime (default: INFO).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse args, run the sandbox runtime, return the exit code."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    runtime = SandboxRuntime(
        url=args.url,
        token=args.token,
        group=args.name,
    )
    try:
        return asyncio.run(runtime.run())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
