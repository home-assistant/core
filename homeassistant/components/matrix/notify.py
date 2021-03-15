"""Support for Matrix notifications."""
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TARGET,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_FILE,
    DOMAIN,
    SERVICE_SEND_FILE,
    SERVICE_SEND_MESSAGE,
    SERVICE_SEND_PHOTO,
    SERVICE_SEND_VIDEO,
)

CONF_DEFAULT_ROOM = "default_room"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_DEFAULT_ROOM): cv.string})


def get_service(hass, config, discovery_info=None):
    """Get the Matrix notification service."""
    return MatrixNotificationService(config[CONF_DEFAULT_ROOM])


class MatrixNotificationService(BaseNotificationService):
    """Send notifications to a Matrix room."""

    def __init__(self, default_room):
        """Set up the Matrix notification service."""
        self._default_room = default_room

    def send_message(self, message="", **kwargs):
        """Send the message to the Matrix server."""
        target_rooms = kwargs.get(ATTR_TARGET) or [self._default_room]

        service_data = {ATTR_TARGET: target_rooms, ATTR_MESSAGE: message}

        return self.hass.services.call(
            DOMAIN, SERVICE_SEND_MESSAGE, service_data=service_data
        )

    def send_photo(self, photo, **kwargs):
        """Send the photo to the Matrix server."""
        target_rooms = kwargs.get(ATTR_TARGET) or [self._default_room]

        service_data = {ATTR_TARGET: target_rooms, ATTR_FILE: photo}

        return self.hass.services.call(
            DOMAIN, SERVICE_SEND_PHOTO, service_data=service_data
        )

    def send_file(self, file, **kwargs):
        """Send the file to the Matrix server."""
        target_rooms = kwargs.get(ATTR_TARGET) or [self._default_room]

        service_data = {ATTR_TARGET: target_rooms, ATTR_FILE: file}

        return self.hass.services.call(
            DOMAIN, SERVICE_SEND_FILE, service_data=service_data
        )

    def send_video(self, video, **kwargs):
        """Send the video to the Matrix server."""
        target_rooms = kwargs.get(ATTR_TARGET) or [self._default_room]

        service_data = {ATTR_TARGET: target_rooms, ATTR_FILE: video}

        return self.hass.services.call(
            DOMAIN, SERVICE_SEND_VIDEO, service_data=service_data
        )
