"""
Support for file notification.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.file/
"""
import logging
import os

import voluptuous as vol

from homeassistant.const import CONF_FILENAME
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

from . import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)

CONF_TIMESTAMP = 'timestamp'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FILENAME): cv.string,
    vol.Optional(CONF_TIMESTAMP, default=False): cv.boolean,
})

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the file notification service."""
    filename = config[CONF_FILENAME]
    timestamp = config[CONF_TIMESTAMP]

    return FileNotificationService(hass, filename, timestamp)


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
                    kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
                    dt_util.utcnow().isoformat(),
                    '-' * 80)
                file.write(title)

            if self.add_timestamp:
                text = '{} {}\n'.format(dt_util.utcnow().isoformat(), message)
            else:
                text = '{}\n'.format(message)
            file.write(text)
