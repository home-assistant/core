"""Validate manifests."""
import pathlib
import sys

from .model import Integration, Config
from . import dependencies, manifest, codeowners

PLUGINS = [
    manifest,
    dependencies,
    codeowners,
]


def get_config() -> Config:
    """Return config."""
    if not pathlib.Path('requirements_all.txt').is_file():
        raise RuntimeError("Run from project root")

    return Config(
        root=pathlib.Path('.'),
        action='validate' if sys.argv[-1] == 'validate' else 'generate',
    )


def main():
    """Validate manifests."""
    try:
        config = get_config()
    except RuntimeError as err:
        print(err)
        return 1

    integrations = Integration.load_dir(
        pathlib.Path('homeassistant/components')
    )
    manifest.validate(integrations, config)
    dependencies.validate(integrations, config)
    codeowners.validate(integrations, config)

    invalid = [itg for itg in integrations.values() if itg.errors]

    print("Integrations:", len(integrations))
    print("Invalid integrations:", len(invalid))

    if not invalid and not config.errors:
        codeowners.generate(integrations, config)
        return 0

    print()

    if config.errors:
        print("Generic errors:")
        for error in config.errors:
            print("*", error)
        print()

    for integration in sorted(invalid, key=lambda itg: itg.domain):
        print(integration.domain)
        for error in integration.errors:
            print("*", error)
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
