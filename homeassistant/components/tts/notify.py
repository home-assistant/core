"""Support notifications through TTS service."""
import logging

import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_NAME
from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv

from . import ATTR_ENTITY_ID, ATTR_LANGUAGE, ATTR_MESSAGE, DOMAIN

CONF_MEDIA_PLAYER = "media_player"
CONF_TTS_SERVICE = "tts_service"

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_TTS_SERVICE): cv.entity_id,
        vol.Required(CONF_MEDIA_PLAYER): cv.entity_id,
        vol.Optional(ATTR_LANGUAGE): cv.string,
    }
)


async def async_get_service(hass, config, discovery_info=None):
    """Return the notify service."""

    return TTSNotificationService(config)


class TTSNotificationService(BaseNotificationService):
    """The TTS Notification Service."""

    def __init__(self, config):
        """Initialize the service."""
        _, self._tts_service = split_entity_id(config[CONF_TTS_SERVICE])
        self._media_player = config[CONF_MEDIA_PLAYER]
        self._language = config.get(ATTR_LANGUAGE)

    async def async_send_message(self, message="", **kwargs):
        """Call TTS service to speak the notification."""
        _LOGGER.debug("%s '%s' on %s", self._tts_service, message, self._media_player)

        data = {
            ATTR_MESSAGE: message,
            ATTR_ENTITY_ID: self._media_player,
        }
        if self._language:
            data[ATTR_LANGUAGE] = self._language

        await self.hass.services.async_call(
            DOMAIN,
            self._tts_service,
            data,
        )
