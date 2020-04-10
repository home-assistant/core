"""Validate manifests."""
import argparse
from pathlib import Path
import sys

from . import clean, download, error, upload


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    parser = argparse.ArgumentParser(description="Home Assistant Scaffolder")
    parser.add_argument("action", type=str, choices=["download", "clean", "upload"])
    parser.add_argument("--debug", action="store_true", help="Enable log output")

    arguments = parser.parse_args()

    return arguments


def main():
    """Run a translation script."""
    if not Path("requirements_all.txt").is_file():
        print("Run from project root")
        return 1

    args = get_arguments()

    if args.action == "download":
        download.run(args)
    elif args.action == "upload":
        upload.run(args)
    elif args.action == "clean":
        clean.run()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except error.ExitApp as err:
        print()
        print(f"Fatal Error: {err.reason}")
        sys.exit(err.exit_code)
