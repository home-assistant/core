"""Validate manifests."""
import argparse
from pathlib import Path
import subprocess
import sys

from . import gather_info, generate, error, docs
from .const import COMPONENT_DIR


TEMPLATES = [
    p.name for p in (Path(__file__).parent / "templates").glob("*") if p.is_dir()
]


def valid_integration(integration):
    """Test if it's a valid integration."""
    if not (COMPONENT_DIR / integration).exists():
        raise argparse.ArgumentTypeError(
            f"The integration {integration} does not exist."
        )

    return integration


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    parser = argparse.ArgumentParser(description="Home Assistant Scaffolder")
    parser.add_argument("template", type=str, choices=TEMPLATES)
    parser.add_argument(
        "--develop", action="store_true", help="Automatically fill in info"
    )
    parser.add_argument(
        "--integration", type=valid_integration, help="Integration to target."
    )

    arguments = parser.parse_args()

    return arguments


def main():
    """Scaffold an integration."""
    if not Path("requirements_all.txt").is_file():
        print("Run from project root")
        return 1

    args = get_arguments()

    info = gather_info.gather_info(args)

    generate.generate(args.template, info)

    # If creating new integration, create config flow too
    if args.template == "integration":
        if info.authentication or not info.discoverable:
            template = "config_flow"
        else:
            template = "config_flow_discovery"

        generate.generate(template, info)

    print("Running hassfest to pick up new information.")
    subprocess.run("python -m script.hassfest", shell=True)
    print()

    print("Running tests")
    print(f"$ pytest -vvv tests/components/{info.domain}")
    if (
        subprocess.run(
            f"pytest -vvv tests/components/{info.domain}", shell=True
        ).returncode
        != 0
    ):
        return 1
    print()

    print(f"Done!")

    docs.print_relevant_docs(args.template, info)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except error.ExitApp as err:
        print()
        print(f"Fatal Error: {err.reason}")
        sys.exit(err.exit_code)
