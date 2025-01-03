"""Start Home Assistant."""

from __future__ import annotations

import argparse
from contextlib import suppress
import faulthandler
import os
import sys
import threading

from .backup_restore import restore_backup
from .const import REQUIRED_PYTHON_VER, RESTART_EXIT_CODE, __version__

FAULT_LOG_FILENAME = "home-assistant.log.fault"


def validate_os() -> None:
    """Ensure Home Assistant runs on supported operating systems."""
    if sys.platform not in {"darwin", "linux"}:
        print(
            "Home Assistant supports only Linux, macOS, and Windows using WSL.",
            file=sys.stderr,
        )
        sys.exit(1)


def validate_python() -> None:
    """Ensure the Python version meets the minimum requirement."""
    if sys.version_info < REQUIRED_PYTHON_VER:
        print(
            f"Home Assistant requires Python {'.'.join(map(str, REQUIRED_PYTHON_VER))} or higher.",
            file=sys.stderr,
        )
        sys.exit(1)


def ensure_config_path(config_dir: str) -> None:
    """Ensure the configuration directory exists and is accessible."""
    from . import config as config_util

    lib_dir = os.path.join(config_dir, "deps")

    if not os.path.isdir(config_dir):
        if config_dir != config_util.get_default_config_dir():
            reason = "is not a directory" if os.path.exists(config_dir) else "does not exist"
            print(f"Fatal Error: Config directory {config_dir} {reason}", file=sys.stderr)
            sys.exit(1)

        try:
            os.mkdir(config_dir)
        except OSError as ex:
            print(f"Fatal Error: Unable to create config directory {config_dir}: {ex}", file=sys.stderr)
            sys.exit(1)

    if not os.path.isdir(lib_dir):
        try:
            os.mkdir(lib_dir)
        except OSError as ex:
            print(f"Fatal Error: Unable to create library directory {lib_dir}: {ex}", file=sys.stderr)
            sys.exit(1)


def get_arguments() -> argparse.Namespace:
    """Parse and return CLI arguments."""
    from . import config as config_util

    parser = argparse.ArgumentParser(
        description="Home Assistant: Observe, Control, Automate.",
        epilog=f"On restart request, exits with code {RESTART_EXIT_CODE}",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "-c",
        "--config",
        default=config_util.get_default_config_dir(),
        help="Directory containing the Home Assistant configuration",
    )
    parser.add_argument("--recovery-mode", action="store_true", help="Start in recovery mode.")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode.")
    parser.add_argument("--open-ui", action="store_true", help="Open the web interface in a browser.")
    parser.add_argument("--skip-pip", action="store_true", help="Skip installing required packages.")
    parser.add_argument(
        "--skip-pip-packages",
        type=lambda arg: arg.split(","),
        default=[],
        help="Skip installation of specific packages.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")
    parser.add_argument(
        "--log-rotate-days", type=int, help="Enable daily log rotation and retain logs for N days."
    )
    parser.add_argument("--log-file", type=str, help="Specify log file. Defaults to CONFIG/home-assistant.log.")
    parser.add_argument("--log-no-color", action="store_true", help="Disable color in logs.")
    parser.add_argument("--script", nargs=argparse.REMAINDER, help="Run an embedded script.")
    parser.add_argument("--ignore-os-check", action="store_true", help="Skip OS validation.")

    return parser.parse_args()


def check_threads() -> None:
    """Log lingering threads after execution."""
    try:
        active_threads = sum(thread.is_alive() and not thread.daemon for thread in threading.enumerate())
        if active_threads > 1:
            print(f"Warning: Found {active_threads} non-daemonic threads.", file=sys.stderr)
    except AssertionError:
        print("Error: Unable to count threads.", file=sys.stderr)


def main() -> int:
    """Entry point for Home Assistant."""
    validate_python()

    args = get_arguments()

    if not args.ignore_os_check:
        validate_os()

    if args.script:
        from . import scripts
        return scripts.run(args.script)

    config_dir = os.path.abspath(os.path.join(os.getcwd(), args.config))
    if restore_backup(config_dir):
        return RESTART_EXIT_CODE

    ensure_config_path(config_dir)

    from . import config, runner

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
        safe_mode=config.safe_mode_enabled(config_dir),
    )

    fault_file_path = os.path.join(config_dir, FAULT_LOG_FILENAME)
    with open(fault_file_path, "a", encoding="utf8") as fault_file:
        faulthandler.enable(fault_file)
        exit_code = runner.run(runtime_conf)
        faulthandler.disable()

    with suppress(FileNotFoundError):
        if os.path.getsize(fault_file_path) == 0:
            os.remove(fault_file_path)

    check_threads()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
