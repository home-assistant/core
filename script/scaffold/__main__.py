"""Validate manifests."""

import argparse
from pathlib import Path
import runpy
import sys

from script.util import valid_integration

from . import docs, error, gather_info, generate
from .model import Info


class _ProcessError(Exception):
    """Raised when a sub-process exits with a non-zero return code."""

    def __init__(self, returncode: int) -> None:
        self.returncode = returncode
        super().__init__(f"Process failed with exit code {returncode}")

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
    """Run a Python module command and handle the result.

    :param name: The name of the command used in reporting.
    :param cmd: The command arguments (must be a ``python -m <module> [args]`` invocation).
    :param info: The Info object.
    :raises _ProcessError: If the command failed.

    If the command was successful print a success message, otherwise
    print an error message and raise a _ProcessError.
    """
    print(f"Command: {' '.join(cmd)}")
    print()

    m_idx = cmd.index("-m") if "-m" in cmd else -1
    module = cmd[m_idx + 1] if m_idx >= 0 else cmd[0]
    module_args = cmd[m_idx + 2:] if m_idx >= 0 else cmd[1:]

    old_argv = sys.argv
    sys.argv = [module, *module_args]
    try:
        runpy.run_module(module, run_name="__main__", alter_sys=True)
        returncode = 0
    except SystemExit as exc:
        returncode = int(exc.code) if exc.code is not None else 0
    finally:
        sys.argv = old_argv

    if returncode == 0:
        print()
        print(f"Completed {name} successfully.")
        print()
        return

    print()
    print(f"Fatal Error: {name} failed with exit code {returncode}")
    print()
    if info.is_new:
        print("This is a bug, please report an issue!")
    else:
        print(
            "This may be an existing issue with your integration,",
            "if so fix and run `script.scaffold` again,",
            "otherwise please report an issue.",
        )
    raise _ProcessError(returncode)


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
            if info.integration_type == "helper":
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
    except _ProcessError as err:
        sys.exit(err.returncode)
    except error.ExitApp as err:
        print()
        print(f"Fatal Error: {err.reason}")
        sys.exit(err.exit_code)
