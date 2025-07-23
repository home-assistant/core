"""Prowl notification service."""

from __future__ import annotations

import asyncio
from functools import partial
import logging

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
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

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

    def __init__(self, hass, api_key):
        """Initialize the service."""
        self._hass = hass
        self._prowl = pyprowl.Prowl(api_key)

    async def async_send_message(self, message, **kwargs):
        """Send the message to the user."""
        data = kwargs.get(ATTR_DATA, {})
        if data is None:
            data = {}

        try:
            async with asyncio.timeout(10):
                await self._hass.async_add_executor_job(
                    partial(
                        self._prowl.notify,
                        appName="Home-Assistant",
                        event=kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
                        description=message,
                        priority=data.get("priority", 0),
                        url=data.get("url"),
                    )
                )
        except TimeoutError:
            _LOGGER.error("Timeout accessing Prowl API")
            raise
        except Exception as ex:
            # pyprowl just specifically raises an Exception with a string at API failures unfortunately.
            if str(ex).startswith("401 "):
                # Bad API key
                _LOGGER.error("Invalid API key for Prowl service")
                raise ConfigEntryAuthFailed from ex
            elif str(ex)[0:3].isdigit():  # noqa: RET506
                # One of the other API errors
                _LOGGER.error("Prowl service returned error: %s", str(ex))
                raise HomeAssistantError from ex
            else:
                _LOGGER.error("Unexpected error when calling Prowl API: %s", str(ex))
                # Not one of the API specific exceptions, so not catching it.
                raise
