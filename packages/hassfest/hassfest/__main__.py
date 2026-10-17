"""Validate custom integrations with the installed Home Assistant version."""

import sys

from .cli import get_config
from .plugins import INTEGRATION_PLUGINS, load_plugins
from .runner import run


def main() -> int:
    """Run standalone hassfest."""
    try:
        config = get_config(INTEGRATION_PLUGINS)
    except RuntimeError as err:
        print(err)
        return 1
    return run(config, load_plugins(config))


if __name__ == "__main__":
    sys.exit(main())
