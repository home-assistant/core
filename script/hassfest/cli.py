"""Run hassfest from the command line."""

import argparse
from functools import partial
from pathlib import Path

from hassfest.model import Config


def valid_integration_path(integration_path: Path | str) -> Path:
    """Test if it's a valid integration."""
    path = Path(integration_path)
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"{integration_path} is not a directory.")

    return path


def validate_plugins(plugin_names: str, *, available: list[str]) -> list[str]:
    """Split and validate plugin names."""
    all_plugin_names = set(available)
    plugins = plugin_names.split(",")
    for plugin in plugins:
        if plugin not in all_plugin_names:
            raise argparse.ArgumentTypeError(f"{plugin} is not a valid plugin name")

    return plugins


def get_config(available: list[str]) -> Config:
    """Return config."""
    parser = argparse.ArgumentParser(description="Hassfest")
    parser.add_argument(
        "--action", type=str, choices=["validate", "generate"], default=None
    )
    parser.add_argument(
        "--integration-path",
        action="append",
        type=valid_integration_path,
        help="Validate a single integration",
    )
    parser.add_argument(
        "--requirements",
        action="store_true",
        help="Validate requirements",
    )
    parser.add_argument(
        "-p",
        "--plugins",
        type=partial(validate_plugins, available=available),
        default=available,
        help="Comma-separated list of plugins to run. Valid plugin names: %(default)s",
    )
    parser.add_argument(
        "--skip-plugins",
        type=partial(validate_plugins, available=available),
        default=[],
        help=(
            f"Comma-separated list of plugins to skip. Valid plugin names: {available}"
        ),
    )
    parser.add_argument(
        "--core-path",
        type=Path,
        default=Path(),
        help="Path to core",
    )
    parsed = parser.parse_args()

    if parsed.action is None:
        parsed.action = "validate" if parsed.integration_path else "generate"

    if parsed.action == "generate" and parsed.integration_path:
        raise RuntimeError(
            "Generate is not allowed when limiting to specific integrations"
        )

    if (
        not parsed.integration_path
        and not (parsed.core_path / "requirements_all.txt").is_file()
    ):
        raise RuntimeError("Run from Home Assistant root")

    if parsed.skip_plugins:
        parsed.plugins = set(parsed.plugins) - set(parsed.skip_plugins)

    return Config(
        root=parsed.core_path.absolute(),
        specific_integrations=parsed.integration_path,
        action=parsed.action,
        requirements=parsed.requirements,
        plugins=set(parsed.plugins),
    )
