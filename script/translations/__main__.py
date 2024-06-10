"""Validate manifests."""

import argparse
import importlib
from pathlib import Path
import sys

from . import error, util


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    return util.get_base_arg_parser().parse_known_args()[0]


def main():
    """Run a translation script."""
    if not Path("requirements_all.txt").is_file():
        print("Run from project root")
        return 1

    args = get_arguments()

    module = importlib.import_module(f".{args.action}", "script.translations")
    return module.run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except error.ExitApp as err:
        print()
        print(f"Fatal Error: {err.reason}")
        sys.exit(err.exit_code)
    except (KeyboardInterrupt, EOFError):
        print()
        print("Aborted!")
        sys.exit(2)
