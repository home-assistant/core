"""Prowl notification service."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pyprowl
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)
_RESOURCE = "https://api.prowlapp.com/publicapi/"

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend({vol.Required(CONF_API_KEY): cv.string})


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> ProwlNotificationService:
    """Get the Prowl notification service."""
    return ProwlNotificationService(hass, config[CONF_API_KEY])


class ProwlNotificationService(BaseNotificationService):
    """Implement the notification service for Prowl."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        """Initialize the service."""
        self._hass = hass
        self._prowl = pyprowl.Prowl(api_key)

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send the message to the user."""
        url = f"{_RESOURCE}add"
        data = kwargs.get(ATTR_DATA)

        if data and data.get("url"):
            url = data["url"]
        try:
            async with asyncio.timeout(10):
                self._prowl.notify(
                    appName="Home-Assistant",
                    event=kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
                    description=message,
                    priority=data["priority"] if data and "priority" in data else 0,
                    url=url,
                )
        except TimeoutError:
            _LOGGER.error("Timeout accessing Prowl at %s", url)
        except Exception as e:  # noqa: BLE001
            # pyprowl just specifically raises an Exception with a string at API failures unfortunately.
            _LOGGER.error(str(e))
