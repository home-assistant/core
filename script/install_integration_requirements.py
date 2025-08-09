"""Install requirements for one or more integrations."""

import argparse
from pathlib import Path
import subprocess
import sys

from .gen_requirements_all import gather_recursive_requirements
from .util import valid_integration


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    parser = argparse.ArgumentParser(
        description="Install requirements for one or more integrations"
    )
    parser.add_argument(
        "integrations",
        nargs="+",
        type=valid_integration,
        help="Integration(s) to target.",
    )

    return parser.parse_args()


def main() -> int | None:
    """Install requirements for the specified integrations."""
    if not Path("requirements_all.txt").is_file():
        print("Run from project root")
        return 1

    args = get_arguments()

    # Gather requirements for all specified integrations
    all_requirements = set()
    for integration in args.integrations:
        requirements = gather_recursive_requirements(integration)
        all_requirements.update(requirements)

    if all_requirements:
        cmd = [
            "uv",
            "pip",
            "install",
            "-c",
            "homeassistant/package_constraints.txt",
            "-U",
            *sorted(all_requirements),  # Sort for consistent output
        ]
        print(" ".join(cmd))
        subprocess.run(
            cmd,
            check=True,
        )
    else:
        print("No requirements to install.")
    return None


if __name__ == "__main__":
    sys.exit(main())
