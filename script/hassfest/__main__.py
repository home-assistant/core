"""Run hassfest with Core's plugin selection and checkout data."""

import sys

from hassfest.runner import run

from .cli import get_config
from .plugins import ALL_PLUGIN_NAMES, load_plugins


def main() -> int:
    """Run hassfest with the selected plugins."""
    try:
        config = get_config(ALL_PLUGIN_NAMES)
    except RuntimeError as err:
        print(err)
        return 1

    return run(config, load_plugins(config))


if __name__ == "__main__":
    sys.exit(main())
