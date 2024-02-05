"""Prowl notification service."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)
_RESOURCE = "https://api.prowlapp.com/publicapi/"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_API_KEY): cv.string})


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> ProwlNotificationService:
    """Get the Prowl notification service."""
    return ProwlNotificationService(hass, config[CONF_API_KEY])


class ProwlNotificationService(BaseNotificationService):
    """Implement the notification service for Prowl."""

    def __init__(self, hass, api_key):
        """Initialize the service."""
        self._hass = hass
        self._api_key = api_key

    async def async_send_message(self, message, **kwargs):
        """Send the message to the user."""
        response = None
        session = None
        url = f"{_RESOURCE}add"
        data = kwargs.get(ATTR_DATA)
        payload = {
            "apikey": self._api_key,
            "application": "Home-Assistant",
            "event": kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
            "description": message,
            "priority": data["priority"] if data and "priority" in data else 0,
        }
        if data and data.get("url"):
            payload["url"] = data["url"]

        _LOGGER.debug("Attempting call Prowl service at %s", url)
        session = async_get_clientsession(self._hass)

        try:
            async with asyncio.timeout(10):
                response = await session.post(url, data=payload)
                result = await response.text()

            if response.status != HTTPStatus.OK or "error" in result:
                _LOGGER.error(
                    "Prowl service returned http status %d, response %s",
                    response.status,
                    result,
                )
        except TimeoutError:
            _LOGGER.error("Timeout accessing Prowl at %s", url)
