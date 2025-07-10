"""Validate manifests."""

import argparse
from pathlib import Path
import subprocess
import sys

from script.util import valid_integration

from . import docs, error, gather_info, generate
from .model import Info

TEMPLATES = [
    p.name for p in (Path(__file__).parent / "templates").glob("*") if p.is_dir()
]


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

    return parser.parse_args()


def run_process(name: str, cmd: list[str], info: Info) -> None:
    """Run a sub process and handle the result.

    :param name: The name of the sub process used in reporting.
    :param cmd: The sub process arguments.
    :param info: The Info object.
    :raises subprocess.CalledProcessError: If the subprocess failed.

    If the sub process was successful print a success message, otherwise
    print an error message and raise a subprocess.CalledProcessError.
    """
    print(f"Command: {' '.join(cmd)}")
    print()
    result: subprocess.CompletedProcess = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        print()
        print(f"Completed {name} successfully.")
        print()
        return

    print()
    print(f"Fatal Error: {name} failed with exit code {result.returncode}")
    print()
    if info.is_new:
        print("This is a bug, please report an issue!")
    else:
        print(
            "This may be an existing issue with your integration,",
            "if so fix and run `script.scaffold` again,",
            "otherwise please report an issue.",
        )
    result.check_returncode()


def main() -> int:
    """Scaffold an integration."""
    if not Path("requirements_all.txt").is_file():
        print("Run from project root")
        return 1

    args = get_arguments()

    info = gather_info.gather_info(args)
    print()

    # If we are calling scaffold on a non-existing integration,
    # We're going to first make it. If we're making an integration,
    # we will also make a config flow to go with it.

    if info.is_new:
        generate.generate("integration", info)

        # If it's a new integration and it's not a config flow,
        # create a config flow too.
        if not args.template.startswith("config_flow"):
            if info.helper:
                template = "config_flow_helper"
            elif info.oauth2:
                template = "config_flow_oauth2"
            elif info.authentication or not info.discoverable:
                template = "config_flow"
            else:
                template = "config_flow_discovery"

            generate.generate(template, info)

    # If we wanted a new integration, we've already done our work.
    if args.template != "integration":
        generate.generate(args.template, info)

    # Always output sub commands as the output will contain useful information if a command fails.
    print("Running hassfest to pick up new information.")
    run_process(
        "hassfest",
        [
            "python",
            "-m",
            "script.hassfest",
            "--integration-path",
            str(info.integration_dir),
            "--skip-plugins",
            "quality_scale",  # Skip quality scale as it will fail for newly generated integrations.
        ],
        info,
    )

    print("Running gen_requirements_all to pick up new information.")
    run_process(
        "gen_requirements_all",
        ["python", "-m", "script.gen_requirements_all"],
        info,
    )

    print("Running translations to pick up new translation strings.")
    run_process(
        "translations",
        [
            "python",
            "-m",
            "script.translations",
            "develop",
            "--integration",
            info.domain,
        ],
        info,
    )

    if args.develop:
        print("Running tests")
        run_process(
            "pytest",
            [
                "python3",
                "-b",
                "-m",
                "pytest",
                "-vvv",
                f"tests/components/{info.domain}",
            ],
            info,
        )

    docs.print_relevant_docs(args.template, info)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as err:
        sys.exit(err.returncode)
    except error.ExitApp as err:
        print()
        print(f"Fatal Error: {err.reason}")
        sys.exit(err.exit_code)
