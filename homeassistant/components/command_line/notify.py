"""
Support for command line notification services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.command_line/
"""
import logging
import subprocess

import voluptuous as vol

from homeassistant.const import CONF_COMMAND, CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import PLATFORM_SCHEMA, BaseNotificationService

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COMMAND): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Command Line notification service."""
    command = config[CONF_COMMAND]

    return CommandLineNotificationService(command)


class CommandLineNotificationService(BaseNotificationService):
    """Implement the notification service for the Command Line service."""

    def __init__(self, command):
        """Initialize the service."""
        self.command = command

    def send_message(self, message="", **kwargs):
        """Send a message to a command line."""
        try:
            proc = subprocess.Popen(self.command, universal_newlines=True,
                                    stdin=subprocess.PIPE, shell=True)
            proc.communicate(input=message)
            if proc.returncode != 0:
                _LOGGER.error("Command failed: %s", self.command)
        except subprocess.SubprocessError:
            _LOGGER.error("Error trying to exec Command: %s", self.command)
