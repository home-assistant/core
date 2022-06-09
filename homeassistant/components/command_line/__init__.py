"""The command_line component."""
from __future__ import annotations

import logging
import subprocess

_LOGGER = logging.getLogger(__name__)


def call_shell_with_timeout(
    command: str, timeout: int, *, log_return_code: bool = True
) -> int:
    """Run a shell command with a timeout.

    If log_return_code is set to False, it will not print an error if a non-zero
    return code is returned.
    """
    try:
        _LOGGER.debug("Running command: %s", command)
        subprocess.check_output(
            command, shell=True, timeout=timeout  # nosec # shell by design
        )
        return 0
    except subprocess.CalledProcessError as proc_exception:
        if log_return_code:
            _LOGGER.error("Command failed: %s", command)
        return proc_exception.returncode
    except subprocess.TimeoutExpired:
        _LOGGER.error("Timeout for command: %s", command)
        return -1
    except subprocess.SubprocessError:
        _LOGGER.error("Error trying to exec command: %s", command)
        return -1


def check_output_or_log(command: str, timeout: int) -> str | None:
    """Run a shell command with a timeout and return the output."""
    try:
        return_value = subprocess.check_output(
            command, shell=True, timeout=timeout  # nosec # shell by design
        )
        return return_value.strip().decode("utf-8")
    except subprocess.CalledProcessError:
        _LOGGER.error("Command failed: %s", command)
    except subprocess.TimeoutExpired:
        _LOGGER.error("Timeout for command: %s", command)
    except subprocess.SubprocessError:
        _LOGGER.error("Error trying to exec command: %s", command)

    return None
