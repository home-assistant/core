"""Support for Matrix notifications."""
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, SERVICE_SEND_IMAGE, SERVICE_SEND_MESSAGE

CONF_DEFAULT_ROOM = "default_room"
CONF_DEFAULT_MARKDOWN = "default_markdown"
CONF_DEFAULT_NOTICE = "default_notice"

ATTR_MARKDOWN = "markdown"
ATTR_NOTICE = "notice"
ATTR_FILE = "file"
ATTR_URL = "url"
ATTR_IMAGE = "image"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEFAULT_ROOM): cv.string,
        vol.Optional(CONF_DEFAULT_MARKDOWN, default=False): cv.boolean,
        vol.Optional(CONF_DEFAULT_NOTICE, default=False): cv.boolean,
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the Matrix notification service."""
    return MatrixNotificationService(
        config[CONF_DEFAULT_ROOM],
        config[CONF_DEFAULT_MARKDOWN],
        config[CONF_DEFAULT_NOTICE],
    )


class MatrixNotificationService(BaseNotificationService):
    """Send notifications to a Matrix room."""

    def __init__(self, default_room, default_markdown, default_notice):
        """Set up the Matrix notification service."""
        self._default_room = default_room
        self._default_markdown = default_markdown
        self._default_notice = default_notice

    def send_message(self, message="", **kwargs):
        """Send the message to the Matrix server."""
        target_rooms = kwargs.get(ATTR_TARGET) or [self._default_room]

        if kwargs.get(ATTR_DATA):
            if "markdown" in kwargs.get(ATTR_DATA):
                markdown = kwargs.get(ATTR_DATA).get(ATTR_MARKDOWN)
            else:
                markdown = self._default_markdown
            if "notice" in kwargs.get(ATTR_DATA):
                notice = kwargs.get(ATTR_DATA).get(ATTR_NOTICE)
            else:
                notice = self._default_notice
        else:
            markdown = self._default_markdown
            notice = self._default_notice

        if kwargs.get(ATTR_TITLE):
            markdown = True
            message = f"""# {kwargs.get(ATTR_TITLE)}

{message}"""

        if kwargs.get(ATTR_DATA) and kwargs.get(ATTR_DATA).get(ATTR_IMAGE):
            _image = kwargs.get(ATTR_DATA).get(ATTR_IMAGE)
            if _image.startswith("file://"):
                _send_image = ATTR_FILE
                _image = _image[6:]
            else:
                _send_image = ATTR_URL
        else:
            _send_image = None

        _response = None
        if _send_image:
            service_data = {ATTR_TARGET: target_rooms, _send_image: _image}

            _response = self.hass.services.call(
                DOMAIN, SERVICE_SEND_IMAGE, service_data=service_data
            )

        if len(message) > 0:
            service_data = {
                ATTR_TARGET: target_rooms,
                ATTR_MESSAGE: message,
                ATTR_MARKDOWN: markdown,
                ATTR_NOTICE: notice,
            }

            _response = self.hass.services.call(
                DOMAIN, SERVICE_SEND_MESSAGE, service_data=service_data
            )
        return _response
