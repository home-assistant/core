"""Flock platform for notify component."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging

import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)
_RESOURCE = "https://api.flock.com/hooks/sendMessage/"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_ACCESS_TOKEN): cv.string})


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> FlockNotificationService:
    """Get the Flock notification service."""
    access_token = config.get(CONF_ACCESS_TOKEN)
    url = f"{_RESOURCE}{access_token}"
    session = async_get_clientsession(hass)

    return FlockNotificationService(url, session)


class FlockNotificationService(BaseNotificationService):
    """Implement the notification service for Flock."""

    def __init__(self, url, session):
        """Initialize the Flock notification service."""
        self._url = url
        self._session = session

    async def async_send_message(self, message, **kwargs):
        """Send the message to the user."""
        payload = {"text": message}

        _LOGGER.debug("Attempting to call Flock at %s", self._url)

        try:
            async with asyncio.timeout(10):
                response = await self._session.post(self._url, json=payload)
                result = await response.json()

            if response.status != HTTPStatus.OK or "error" in result:
                _LOGGER.error(
                    "Flock service returned HTTP status %d, response %s",
                    response.status,
                    result,
                )
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout accessing Flock at %s", self._url)
