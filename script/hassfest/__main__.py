"""Validate manifests."""
from __future__ import annotations

import argparse
import pathlib
import sys
from time import monotonic

from . import (
    application_credentials,
    bluetooth,
    codeowners,
    config_flow,
    config_schema,
    coverage,
    dependencies,
    dhcp,
    json,
    manifest,
    metadata,
    mqtt,
    mypy_config,
    recorder,
    requirements,
    services,
    ssdp,
    translations,
    usb,
    zeroconf,
)
from .model import Config, Integration

INTEGRATION_PLUGINS = [
    application_credentials,
    bluetooth,
    codeowners,
    config_schema,
    dependencies,
    dhcp,
    json,
    manifest,
    mqtt,
    recorder,
    requirements,
    services,
    ssdp,
    translations,
    usb,
    zeroconf,
    config_flow,  # This needs to run last, after translations are processed
]
HASS_PLUGINS = [
    coverage,
    mypy_config,
    metadata,
]

ALL_PLUGIN_NAMES = [
    plugin.__name__.rsplit(".", maxsplit=1)[-1]
    for plugin in (*INTEGRATION_PLUGINS, *HASS_PLUGINS)
]


def valid_integration_path(integration_path: pathlib.Path | str) -> pathlib.Path:
    """Test if it's a valid integration."""
    path = pathlib.Path(integration_path)
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"{integration_path} is not a directory.")

    return path


def validate_plugins(plugin_names: str) -> list[str]:
    """Split and validate plugin names."""
    all_plugin_names = set(ALL_PLUGIN_NAMES)
    plugins = plugin_names.split(",")
    for plugin in plugins:
        if plugin not in all_plugin_names:
            raise argparse.ArgumentTypeError(f"{plugin} is not a valid plugin name")

    return plugins


def get_config() -> Config:
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
        type=validate_plugins,
        default=ALL_PLUGIN_NAMES,
        help="Comma-separate list of plugins to run. Valid plugin names: %(default)s",
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
        and not pathlib.Path("requirements_all.txt").is_file()
    ):
        raise RuntimeError("Run from Home Assistant root")

    return Config(
        root=pathlib.Path(".").absolute(),
        specific_integrations=parsed.integration_path,
        action=parsed.action,
        requirements=parsed.requirements,
        plugins=set(parsed.plugins),
    )


def main() -> int:
    """Validate manifests."""
    try:
        config = get_config()
    except RuntimeError as err:
        print(err)
        return 1

    plugins = [*INTEGRATION_PLUGINS]

    if config.specific_integrations:
        integrations = {}

        for int_path in config.specific_integrations:
            integration = Integration(int_path)
            integration.load_manifest()
            integrations[integration.domain] = integration

    else:
        integrations = Integration.load_dir(pathlib.Path("homeassistant/components"))
        plugins += HASS_PLUGINS

    for plugin in plugins:
        plugin_name = plugin.__name__.rsplit(".", maxsplit=1)[-1]
        if plugin_name not in config.plugins:
            continue
        try:
            start = monotonic()
            print(f"Validating {plugin_name}...", end="", flush=True)
            if (
                plugin is requirements
                and config.requirements
                and not config.specific_integrations
            ):
                print()
            plugin.validate(integrations, config)
            print(f" done in {monotonic() - start:.2f}s")
        except RuntimeError as err:
            print()
            print()
            print("Error!")
            print(err)
            return 1

    # When we generate, all errors that are fixable will be ignored,
    # as generating them will be fixed.
    if config.action == "generate":
        general_errors = [err for err in config.errors if not err.fixable]
        invalid_itg = [
            itg
            for itg in integrations.values()
            if any(not error.fixable for error in itg.errors)
        ]
    else:
        # action == validate
        general_errors = config.errors
        invalid_itg = [itg for itg in integrations.values() if itg.errors]

    warnings_itg = [itg for itg in integrations.values() if itg.warnings]

    print()
    print("Integrations:", len(integrations))
    print("Invalid integrations:", len(invalid_itg))
    print()

    if not invalid_itg and not general_errors:
        print_integrations_status(config, warnings_itg, show_fixable_errors=False)

        if config.action == "generate":
            for plugin in plugins:
                plugin_name = plugin.__name__.rsplit(".", maxsplit=1)[-1]
                if plugin_name not in config.plugins:
                    continue
                if hasattr(plugin, "generate"):
                    plugin.generate(integrations, config)
        return 0

    if config.action == "generate":
        print("Found errors. Generating files canceled.")
        print()

    if general_errors:
        print("General errors:")
        for error in general_errors:
            print("*", error)
        print()

    invalid_itg.extend(itg for itg in warnings_itg if itg not in invalid_itg)

    print_integrations_status(config, invalid_itg, show_fixable_errors=False)

    return 1


def print_integrations_status(
    config: Config,
    integrations: list[Integration],
    *,
    show_fixable_errors: bool = True,
) -> None:
    """Print integration status."""
    for integration in sorted(integrations, key=lambda itg: itg.domain):
        extra = f" - {integration.path}" if config.specific_integrations else ""
        print(f"Integration {integration.domain}{extra}:")
        for error in integration.errors:
            if show_fixable_errors or not error.fixable:
                print("*", "[ERROR]", error)
        for warning in integration.warnings:
            print("*", "[WARNING]", warning)
        print()


if __name__ == "__main__":
    sys.exit(main())
