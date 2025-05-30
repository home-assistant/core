"""Prowl notification service."""

from __future__ import annotations

import asyncio
from functools import partial
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import API_URL

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend({vol.Required(CONF_API_KEY): cv.string})


class LegacyProwlNotificationService(BaseNotificationService):
    """Provides the legacy notification service for Prowl."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        """Initialize the service."""
        self._hass = hass
        self._prowl = pyprowl.Prowl(api_key)

    async def async_verify_key(self) -> bool:
        """Validate API key."""
        try:
            async with asyncio.timeout(10):
                await self._hass.async_add_executor_job(self._prowl.verify_key)
                return True
        except TimeoutError:
            raise
        except Exception as ex:
            # pyprowl just specifically raises an Exception with a string at API failures unfortunately.
            if str(ex).startswith("401 "):
                # Bad API key
                return False
            elif str(ex)[0:3].isdigit():  # noqa: RET505
                # One of the other API errors
                raise HomeAssistantError from ex
            else:
                # Not one of the API specific exceptions, so not catching it.
                raise

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Call the new entity service to send the message."""
        url = None
        data = kwargs.get(ATTR_DATA)

        if data and data.get("url"):
            url = data["url"]
        try:
            async with asyncio.timeout(10):
                await self._hass.async_add_executor_job(
                    partial(
                        self._prowl.notify,
                        appName="Home-Assistant",
                        event=kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
                        description=message,
                        priority=data["priority"] if data and "priority" in data else 0,
                        url=url,
                    )
                )
        except TimeoutError:
            _LOGGER.exception("Timeout accessing Prowl at %s", API_URL)
            raise
        except Exception as ex:
            # pyprowl just specifically raises an Exception with a string at API failures unfortunately.
            if str(ex).startswith("401 "):
                # Bad API key
                raise ConfigEntryAuthFailed from ex
            elif str(ex)[0:3].isdigit():  # noqa: RET506
                # One of the other API errors
                raise HomeAssistantError from ex
            else:
                # Not one of the API specific exceptions, so not catching it.
                raise


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> LegacyProwlNotificationService | None:
    """Convert any YAML entries into ConfigFlow."""
    return LegacyProwlNotificationService(hass, config[CONF_API_KEY])


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notify entities."""
    prowl = entry.runtime_data
    async_add_entities([prowl])
