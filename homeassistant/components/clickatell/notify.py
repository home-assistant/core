"""Clickatell platform for notify component."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientSession
import async_timeout
import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_API_KEY, CONF_RECIPIENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "clickatell"

BASE_API_URL = "https://platform.clickatell.com/messages/http/send"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_API_KEY): cv.string, vol.Required(CONF_RECIPIENT): cv.string}
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> ClickatellNotificationService:
    """Get the Clickatell notification service."""
    key = config.get(CONF_API_KEY)
    url = f"{BASE_API_URL}{key}"
    session = async_get_clientsession(hass)

    return ClickatellNotificationService(config, url, session)


class ClickatellNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Clickatell service."""

    def __init__(self, config: ConfigType, url: str, session: ClientSession) -> None:
        """Initialize the service."""
        self.api_key: str = config[CONF_API_KEY]
        self.recipient: str = config[CONF_RECIPIENT]
        self._url = url
        self._session = session

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""
        data = {"apiKey": self.api_key, "to": self.recipient, "content": message}

        try:
            async with async_timeout.timeout(5):
                resp = await self._session.post(BASE_API_URL, params=data)
            if resp.status not in (HTTPStatus.OK, HTTPStatus.ACCEPTED):
                _LOGGER.error("Error %s : %s", resp.status, resp.text)
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout accessing clickatell at %s", self._url)
