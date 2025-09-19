"""Prowl notification service."""

from __future__ import annotations

import asyncio
from functools import partial
import logging
from typing import Any

import prowlpy
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
    NotifyEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend({vol.Required(CONF_API_KEY): cv.string})


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> LegacyProwlNotificationService:
    """Get the Prowl notification service."""
    return LegacyProwlNotificationService(hass, config[CONF_API_KEY])


class LegacyProwlNotificationService(BaseNotificationService):
    """Implement the notification service for Prowl.

    This class is used for legacy configuration via configuration.yaml
    """

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        """Initialize the service."""
        self._hass = hass
        self._prowl = prowlpy.Prowl(api_key)

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send the message to the user."""
        data = kwargs.get(ATTR_DATA, {})
        if data is None:
            data = {}

        try:
            async with asyncio.timeout(10):
                await self._hass.async_add_executor_job(
                    partial(
                        self._prowl.send,
                        application="Home-Assistant",
                        event=kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
                        description=message,
                        priority=data.get("priority", 0),
                        url=data.get("url"),
                    )
                )
        except TimeoutError as ex:
            _LOGGER.error("Timeout accessing Prowl API")
            raise HomeAssistantError("Timeout accessing Prowl API") from ex
        except prowlpy.APIError as ex:
            if str(ex).startswith("Invalid API key"):
                _LOGGER.error("Invalid API key for Prowl service")
                raise HomeAssistantError("Invalid API key for Prowl service") from ex
            if str(ex).startswith("Not accepted"):
                _LOGGER.error("Prowl returned: exceeded rate limit")
                raise HomeAssistantError(
                    "Prowl service reported: exceeded rate limit"
                ) from ex
            _LOGGER.error("Unexpected error when calling Prowl API: %s", str(ex))
            raise HomeAssistantError("Unexpected error when calling Prowl API") from ex


class ProwlNotificationEntity(NotifyEntity):
    """Implement the notification service for Prowl.

    This class is used for Prowl config entries.
    """

    def __init__(self, hass: HomeAssistant, name: str, api_key: str) -> None:
        """Initialize the service."""
        self._hass = hass
        self._prowl = prowlpy.Prowl(api_key)
        self._attr_name = name
        self._attr_unique_id = name

    async def async_verify_key(self) -> bool:
        """Validate API key."""
        try:
            async with asyncio.timeout(10):
                await self._hass.async_add_executor_job(self._prowl.verify_key)
                return True
        except prowlpy.APIError as ex:
            if str(ex).startswith("Invalid API key"):
                return False
            raise

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send the message."""
        try:
            async with asyncio.timeout(10):
                await self._hass.async_add_executor_job(
                    partial(
                        self._prowl.post,
                        appName="Home-Assistant",
                        event=title or ATTR_TITLE_DEFAULT,
                        description=message,
                        priority=0,
                    )
                )
        except TimeoutError as ex:
            _LOGGER.error("Timeout accessing Prowl API")
            raise HomeAssistantError("Timeout accessing Prowl API") from ex
        except prowlpy.APIError as ex:
            if str(ex).startswith("Invalid API key"):
                _LOGGER.error("Invalid API key for Prowl service")
                raise HomeAssistantError("Invalid API key for Prowl service") from ex
            if str(ex).startswith("Not accepted"):
                _LOGGER.error("Prowl returned: exceeded rate limit")
                raise HomeAssistantError(
                    "Prowl service reported: exceeded rate limit"
                ) from ex
            _LOGGER.error("Unexpected error when calling Prowl API: %s", str(ex))
            raise HomeAssistantError("Unexpected error when calling Prowl API") from ex


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notify entities."""
    prowl = entry.runtime_data
    async_add_entities([prowl])
