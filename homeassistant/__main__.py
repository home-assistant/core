"""Start Home Assistant."""

from __future__ import annotations

import argparse
from contextlib import suppress
import faulthandler
import os
import sys
import threading

from .const import REQUIRED_PYTHON_VER, RESTART_EXIT_CODE, __version__

FAULT_LOG_FILENAME = "home-assistant.log.fault"


def validate_os() -> None:
    """Validate that Home Assistant is running in a supported operating system."""
    if not sys.platform.startswith(("darwin", "linux")):
        print(
            "Home Assistant only supports Linux, OSX and Windows using WSL",
            file=sys.stderr,
        )
        sys.exit(1)


def validate_python() -> None:
    """Validate that the right Python version is running."""
    if sys.version_info[:3] < REQUIRED_PYTHON_VER:
        print(
            "Home Assistant requires at least Python "
            f"{REQUIRED_PYTHON_VER[0]}.{REQUIRED_PYTHON_VER[1]}.{REQUIRED_PYTHON_VER[2]}",
            file=sys.stderr,
        )
        sys.exit(1)


def ensure_config_path(config_dir: str) -> None:
    """Validate the configuration directory."""
    # pylint: disable-next=import-outside-toplevel
    from . import config as config_util

    lib_dir = os.path.join(config_dir, "deps")

    # Test if configuration directory exists
    if not os.path.isdir(config_dir):
        if config_dir != config_util.get_default_config_dir():
            if os.path.exists(config_dir):
                reason = "is not a directory"
            else:
                reason = "does not exist"
            print(
                f"Fatal Error: Specified configuration directory {config_dir} {reason}",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            os.mkdir(config_dir)
        except OSError as ex:
            print(
                "Fatal Error: Unable to create default configuration "
                f"directory {config_dir}: {ex}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Test if library directory exists
    if not os.path.isdir(lib_dir):
        try:
            os.mkdir(lib_dir)
        except OSError as ex:
            print(
                f"Fatal Error: Unable to create library directory {lib_dir}: {ex}",
                file=sys.stderr,
            )
            sys.exit(1)


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    # pylint: disable-next=import-outside-toplevel
    from . import config as config_util

    parser = argparse.ArgumentParser(
        description="Home Assistant: Observe, Control, Automate.",
        epilog=f"If restart is requested, exits with code {RESTART_EXIT_CODE}",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "-c",
        "--config",
        metavar="path_to_config_dir",
        default=config_util.get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration",
    )
    parser.add_argument(
        "--recovery-mode",
        action="store_true",
        help="Start Home Assistant in recovery mode",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Start Home Assistant in debug mode"
    )
    parser.add_argument(
        "--open-ui", action="store_true", help="Open the webinterface in a browser"
    )

    skip_pip_group = parser.add_mutually_exclusive_group()
    skip_pip_group.add_argument(
        "--skip-pip",
        action="store_true",
        help="Skips pip install of required packages on startup",
    )
    skip_pip_group.add_argument(
        "--skip-pip-packages",
        metavar="package_names",
        type=lambda arg: arg.split(","),
        default=[],
        help="Skip pip install of specific packages on startup",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging to file."
    )
    parser.add_argument(
        "--log-rotate-days",
        type=int,
        default=None,
        help="Enables daily log rotation and keeps up to the specified days",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log file to write to.  If not set, CONFIG/home-assistant.log is used",
    )
    parser.add_argument(
        "--log-no-color", action="store_true", help="Disable color logs"
    )
    parser.add_argument(
        "--script", nargs=argparse.REMAINDER, help="Run one of the embedded scripts"
    )
    parser.add_argument(
        "--ignore-os-check",
        action="store_true",
        help="Skips validation of operating system",
    )

    return parser.parse_args()


def check_threads() -> None:
    """Check if there are any lingering threads."""
    try:
        nthreads = sum(
            thread.is_alive() and not thread.daemon for thread in threading.enumerate()
        )
        if nthreads > 1:
            sys.stderr.write(f"Found {nthreads} non-daemonic threads.\n")

    # Somehow we sometimes seem to trigger an assertion in the python threading
    # module. It seems we find threads that have no associated OS level thread
    # which are not marked as stopped at the python level.
    except AssertionError:
        sys.stderr.write("Failed to count non-daemonic threads.\n")


def main() -> int:
    """Start Home Assistant."""
    validate_python()

    args = get_arguments()

    if not args.ignore_os_check:
        validate_os()

    if args.script is not None:
        # pylint: disable-next=import-outside-toplevel
        from . import scripts

        return scripts.run(args.script)

    config_dir = os.path.abspath(os.path.join(os.getcwd(), args.config))
    ensure_config_path(config_dir)

    # pylint: disable-next=import-outside-toplevel
    from . import config, runner

    safe_mode = config.safe_mode_enabled(config_dir)

    runtime_conf = runner.RuntimeConfig(
        config_dir=config_dir,
        verbose=args.verbose,
        log_rotate_days=args.log_rotate_days,
        log_file=args.log_file,
        log_no_color=args.log_no_color,
        skip_pip=args.skip_pip,
        skip_pip_packages=args.skip_pip_packages,
        recovery_mode=args.recovery_mode,
        debug=args.debug,
        open_ui=args.open_ui,
        safe_mode=safe_mode,
    )

    fault_file_name = os.path.join(config_dir, FAULT_LOG_FILENAME)
    with open(fault_file_name, mode="a", encoding="utf8") as fault_file:
        faulthandler.enable(fault_file)
        exit_code = runner.run(runtime_conf)
        faulthandler.disable()

    # It's possible for the fault file to disappear, so suppress obvious errors
    with suppress(FileNotFoundError):
        if os.path.getsize(fault_file_name) == 0:
            os.remove(fault_file_name)

    check_threads()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
