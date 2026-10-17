"""Run hassfest from the command line."""

import argparse
from functools import partial
from pathlib import Path

from .model import Config


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


def get_config(available: list[str], *, standalone: bool = False) -> Config:
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
        default=None if standalone else Path(),
        help="Path to core",
    )
    parsed = parser.parse_args()

    if standalone and not parsed.integration_path:
        parser.error("--integration-path is required for standalone validation")

    requirements_path = None
    if standalone and parsed.core_path is None:
        import homeassistant  # noqa: PLC0415

        parsed.core_path = Path(homeassistant.__file__).parent.parent
        requirements_path = Path(__file__).parent / "_data"
        if not all(
            (requirements_path / filename).is_file()
            for filename in ("requirements.txt", "requirements_all.txt")
        ):
            raise RuntimeError(
                "Bundled requirements are missing; build and install hassfest first"
            )
    elif standalone and not all(
        (parsed.core_path / filename).is_file()
        for filename in ("requirements.txt", "requirements_all.txt")
    ):
        raise RuntimeError("--core-path must point to a Home Assistant checkout")

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
        requirements_path=requirements_path,
        specific_integrations=parsed.integration_path,
        action=parsed.action,
        requirements=parsed.requirements,
        plugins=set(parsed.plugins),
    )
