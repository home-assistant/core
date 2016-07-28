"""
Support for command line notification services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.command_line/
"""
import logging
import subprocess
from homeassistant.const import CONF_NAME
from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the Command Line notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['command']},
                           _LOGGER):
        return False

    command = config['command']

    add_devices([CommandLineNotificationService(config.get(CONF_NAME),
                                                command)])


# pylint: disable=too-few-public-methods,abstract-method
class CommandLineNotificationService(BaseNotificationService):
    """Implement the notification service for the Command Line service."""

    def __init__(self, name, command):
        """Initialize the service."""
        self.command = command
        self._name = name

    @property
    def name(self):
        """Return name of notification entity."""
        return self._name

    def send_message(self, message, **kwargs):
        """Send a message to a command line."""
        try:
            proc = subprocess.Popen(self.command, universal_newlines=True,
                                    stdin=subprocess.PIPE, shell=True)
            proc.communicate(input=message)
            if proc.returncode != 0:
                _LOGGER.error('Command failed: %s', self.command)
        except subprocess.SubprocessError:
            _LOGGER.error('Error trying to exec Command: %s', self.command)
