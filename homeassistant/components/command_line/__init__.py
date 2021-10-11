"""The command_line component."""

import logging
import subprocess

from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)


def call_shell_with_returncode(command, timeout):
    """Run a shell command with a timeout.

    If log_return_code is set to False, it will not print an error if a non-zero
    return code is returned.
    """
    try:
        subprocess.check_output(
            command, shell=True, timeout=timeout  # nosec # shell by design
        )
        return 0
    except subprocess.CalledProcessError as proc_exception:
        _LOGGER.error("Command failed: %s", command)
        return proc_exception.returncode
    except subprocess.TimeoutExpired:
        _LOGGER.error("Timeout for command: %s", command)
        return -1
    except subprocess.SubprocessError:
        _LOGGER.error("Error trying to exec command: %s", command)
        return -1


def call_shell_with_value(command, timeout):
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


class CommandData:
    """The class for handling the data retrieval."""

    def __init__(self, hass, command, command_timeout):
        """Initialize the data object."""
        self.value = None
        self.hass = hass
        self.command: template.Template = command
        if self.command and self.hass:
            self.command.hass = self.hass
        self.timeout = command_timeout

    def update(self, with_value):
        """Get the latest data with a shell command."""
        try:
            command = self.command.render()
        except TemplateError as ex:
            _LOGGER.exception("Error rendering command template: %s", ex)
            return None if with_value else -1

        _LOGGER.debug("Running command: %s", command)
        if with_value:
            self.value = call_shell_with_value(command, self.timeout)
        else:
            self.value = call_shell_with_returncode(command, self.timeout)

        return self.value
