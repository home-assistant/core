"""
Support for file notification.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.file/
"""
import logging
import os

import homeassistant.util.dt as dt_util
from homeassistant.components.notify import (
    ATTR_TITLE, DOMAIN, BaseNotificationService)
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """Get the file notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['filename',
                                     'timestamp']},
                           _LOGGER):
        return None

    filename = config['filename']
    timestamp = config['timestamp']

    return FileNotificationService(hass, filename, timestamp)


# pylint: disable=too-few-public-methods
class FileNotificationService(BaseNotificationService):
    """Implement the notification service for the File service."""

    def __init__(self, hass, filename, add_timestamp):
        """Initialize the service."""
        self.filepath = os.path.join(hass.config.config_dir, filename)
        self.add_timestamp = add_timestamp

    def send_message(self, message="", **kwargs):
        """Send a message to a file."""
        with open(self.filepath, 'a') as file:
            if os.stat(self.filepath).st_size == 0:
                title = '{} notifications (Log started: {})\n{}\n'.format(
                    kwargs.get(ATTR_TITLE),
                    dt_util.utcnow().isoformat(),
                    '-' * 80)
                file.write(title)

            if self.add_timestamp == 1:
                text = '{} {}\n'.format(dt_util.utcnow().isoformat(), message)
                file.write(text)
            else:
                text = '{}\n'.format(message)
                file.write(text)
