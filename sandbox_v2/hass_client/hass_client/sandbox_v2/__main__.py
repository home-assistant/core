"""Entry point for ``python -m hass_client.sandbox_v2``.

The Sandbox v2 manager spawns this module as a subprocess. CLI arguments
mirror what the websocket client will need in Phase 4 so the manager-side
command line is stable across phases.
"""

import argparse
import asyncio
import logging
import sys

from hass_client.sandbox import SandboxRuntime, SharingConfig


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hass_client.sandbox_v2",
        description="Sandbox v2 runtime process.",
    )
    parser.add_argument(
        "--group",
        required=True,
        help="Sandbox group name (e.g. main, built-in, custom)",
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
    # Phase 7: opt-in core-data sharing flags. Default off; the sandbox
    # only subscribes to main's bus when explicitly enabled (see
    # SandboxGroupConfig). Stored on the runtime as a SharingConfig so
    # later phases can branch on them.
    parser.add_argument(
        "--share-states",
        action="store_true",
        help="Subscribe to main's state stream from inside the sandbox.",
    )
    parser.add_argument(
        "--share-entity-registry",
        action="store_true",
        help="Mirror main's entity registry into the sandbox.",
    )
    parser.add_argument(
        "--share-areas",
        action="store_true",
        help="Mirror main's area registry into the sandbox.",
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
        group=args.group,
        sharing=SharingConfig(
            share_states=args.share_states,
            share_entity_registry=args.share_entity_registry,
            share_areas=args.share_areas,
        ),
    )
    try:
        return asyncio.run(runtime.run())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
