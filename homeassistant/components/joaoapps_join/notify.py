"""Support for Join notifications."""
import logging

from pyjoin import get_devices, send_notification
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE_ID = "device_id"
CONF_DEVICE_IDS = "device_ids"
CONF_DEVICE_NAMES = "device_names"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_DEVICE_ID): cv.string,
        vol.Optional(CONF_DEVICE_IDS): cv.string,
        vol.Optional(CONF_DEVICE_NAMES): cv.string,
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the Join notification service."""
    api_key = config.get(CONF_API_KEY)
    device_id = config.get(CONF_DEVICE_ID)
    device_ids = config.get(CONF_DEVICE_IDS)
    device_names = config.get(CONF_DEVICE_NAMES)
    if api_key:
        if not get_devices(api_key):
            _LOGGER.error("Error connecting to Join. Check the API key")
            return False
    if device_id is None and device_ids is None and device_names is None:
        _LOGGER.error(
            "No device was provided. Please specify device_id"
            ", device_ids, or device_names"
        )
        return False
    return JoinNotificationService(api_key, device_id, device_ids, device_names)


class JoinNotificationService(BaseNotificationService):
    """Implement the notification service for Join."""

    def __init__(self, api_key, device_id, device_ids, device_names):
        """Initialize the service."""
        self._api_key = api_key
        self._device_id = device_id
        self._device_ids = device_ids
        self._device_names = device_names

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""

        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA) or {}
        send_notification(
            device_id=self._device_id,
            device_ids=self._device_ids,
            device_names=self._device_names,
            text=message,
            title=title,
            icon=data.get("icon"),
            smallicon=data.get("smallicon"),
            image=data.get("image"),
            sound=data.get("sound"),
            notification_id=data.get("notification_id"),
            url=data.get("url"),
            tts=data.get("tts"),
            tts_language=data.get("tts_language"),
            vibration=data.get("vibration"),
            actions=data.get("actions"),
            api_key=self._api_key,
        )
