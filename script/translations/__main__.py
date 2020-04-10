"""Validate manifests."""
import argparse
from pathlib import Path
import sys

from . import clean, develop, download, error, upload, util


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    return util.get_base_arg_parser().parse_known_args()[0]


def main():
    """Run a translation script."""
    if not Path("requirements_all.txt").is_file():
        print("Run from project root")
        return 1

    args = get_arguments()

    if args.action == "download":
        download.run()
    elif args.action == "upload":
        upload.run()
    elif args.action == "clean":
        clean.run()
    elif args.action == "develop":
        develop.run()

    return 0


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
