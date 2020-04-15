"""Validate manifests."""
import pathlib
import sys
from time import monotonic

from . import (
    codeowners,
    config_flow,
    coverage,
    dependencies,
    manifest,
    services,
    ssdp,
    translations,
    zeroconf,
)
from .model import Config, Integration

PLUGINS = [
    codeowners,
    config_flow,
    coverage,
    dependencies,
    manifest,
    services,
    ssdp,
    translations,
    zeroconf,
]


def get_config() -> Config:
    """Return config."""
    if not pathlib.Path("requirements_all.txt").is_file():
        raise RuntimeError("Run from project root")

    return Config(
        root=pathlib.Path(".").absolute(),
        action="validate" if sys.argv[-1] == "validate" else "generate",
    )


def main():
    """Validate manifests."""
    try:
        config = get_config()
    except RuntimeError as err:
        print(err)
        return 1

    integrations = Integration.load_dir(pathlib.Path("homeassistant/components"))

    for plugin in PLUGINS:
        try:
            start = monotonic()
            print(f"Validating {plugin.__name__.split('.')[-1]}...", end="", flush=True)
            plugin.validate(integrations, config)
            print(" done in {:.2f}s".format(monotonic() - start))
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

    print("Integrations:", len(integrations))
    print("Invalid integrations:", len(invalid_itg))

    if not invalid_itg and not general_errors:
        for plugin in PLUGINS:
            if hasattr(plugin, "generate"):
                plugin.generate(integrations, config)

        return 0

    print()
    if config.action == "generate":
        print("Found errors. Generating files canceled.")
        print()

    if general_errors:
        print("General errors:")
        for error in general_errors:
            print("*", error)
        print()

    for integration in sorted(invalid_itg, key=lambda itg: itg.domain):
        print(f"Integration {integration.domain}:")
        for error in integration.errors:
            print("*", error)
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
