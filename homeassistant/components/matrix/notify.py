"""Support for Matrix notifications."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (ATTR_TARGET, PLATFORM_SCHEMA,
                                             BaseNotificationService,
                                             ATTR_MESSAGE)

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_ROOM = 'default_room'

DOMAIN = 'matrix'
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEFAULT_ROOM): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Matrix notification service."""
    return MatrixNotificationService(config.get(CONF_DEFAULT_ROOM))


class MatrixNotificationService(BaseNotificationService):
    """Send Notifications to a Matrix Room."""

    def __init__(self, default_room):
        """Set up the notification service."""
        self._default_room = default_room

    def send_message(self, message="", **kwargs):
        """Send the message to the matrix server."""
        target_rooms = kwargs.get(ATTR_TARGET) or [self._default_room]

        service_data = {
            ATTR_TARGET: target_rooms,
            ATTR_MESSAGE: message
        }

        return self.hass.services.call(
            DOMAIN, 'send_message', service_data=service_data)
