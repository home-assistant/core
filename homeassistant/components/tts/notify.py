"""Support notifications through TTS service."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import ATTR_ENTITY_ID, CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant, split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import ATTR_LANGUAGE, ATTR_MEDIA_PLAYER_ENTITY_ID, ATTR_MESSAGE, DOMAIN

CONF_MEDIA_PLAYER = "media_player"
CONF_TTS_SERVICE = "tts_service"
ENTITY_LEGACY_PROVIDER_GROUP = "entity_or_legacy_provider"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Exclusive(CONF_TTS_SERVICE, ENTITY_LEGACY_PROVIDER_GROUP): cv.entity_id,
        vol.Exclusive(CONF_ENTITY_ID, ENTITY_LEGACY_PROVIDER_GROUP): cv.entities_domain(
            DOMAIN
        ),
        vol.Required(CONF_MEDIA_PLAYER): cv.entity_id,
        vol.Optional(ATTR_LANGUAGE): cv.string,
    }
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> TTSNotificationService:
    """Return the notify service."""

    return TTSNotificationService(config)


class TTSNotificationService(BaseNotificationService):
    """The TTS Notification Service."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the service."""
        self._target: str | None = None
        self._tts_service: str | None = None
        if entity_id := config.get(CONF_ENTITY_ID):
            self._target = entity_id
        else:
            _, self._tts_service = split_entity_id(config[CONF_TTS_SERVICE])
        self._media_player = config[CONF_MEDIA_PLAYER]
        self._language = config.get(ATTR_LANGUAGE)

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Call TTS service to speak the notification."""
        _LOGGER.debug("%s '%s' on %s", self._tts_service, message, self._media_player)

        data = {
            ATTR_MESSAGE: message,
        }
        service_name = ""

        if self._tts_service:
            data[ATTR_ENTITY_ID] = self._media_player
            service_name = self._tts_service
        elif self._target:
            data[ATTR_ENTITY_ID] = self._target
            data[ATTR_MEDIA_PLAYER_ENTITY_ID] = self._media_player
            service_name = "speak"
        if self._language:
            data[ATTR_LANGUAGE] = self._language

        await self.hass.services.async_call(
            DOMAIN,
            service_name,
            data,
        )
