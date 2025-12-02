"""Prowl notification service."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
import prowlpy
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
    NotifyEntity,
    migrate_notify_issue,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend({vol.Required(CONF_API_KEY): cv.string})


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> ProwlNotificationService:
    """Get the Prowl notification service."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2026.04.01",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="prowl_yaml_deprecated",
    )

    return ProwlNotificationService(hass, config[CONF_API_KEY], get_async_client(hass))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notify entities."""
    prowl = ProwlNotificationEntity(
        hass, entry.title, entry.data[CONF_API_KEY], get_async_client(hass)
    )
    async_add_entities([prowl])


class ProwlNotificationService(BaseNotificationService):
    """Implement the notification service for Prowl.

    This class is used for legacy configuration via configuration.yaml
    """

    def __init__(
        self, hass: HomeAssistant, api_key: str, httpx_client: httpx.AsyncClient
    ) -> None:
        """Initialize the service."""
        self._hass = hass
        self._prowl = prowlpy.AsyncProwl(api_key, client=httpx_client)

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send the message to the user."""
        migrate_notify_issue(self._hass, DOMAIN, DOMAIN, "2026.04.01", DOMAIN)

        data = kwargs.get(ATTR_DATA, {})
        if data is None:
            data = {}

        try:
            async with asyncio.timeout(10):
                await self._prowl.post(
                    application="Home-Assistant",
                    event=kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
                    description=message,
                    priority=data.get("priority", 0),
                    url=data.get("url"),
                )
        except TimeoutError as ex:
            _LOGGER.error("Timeout accessing Prowl API")
            raise HomeAssistantError("Timeout accessing Prowl API") from ex
        except prowlpy.InvalidAPIKeyError as ex:
            _LOGGER.error("Invalid API key for Prowl service")
            raise HomeAssistantError("Invalid API key for Prowl service") from ex
        except prowlpy.RateLimitExceededError as ex:
            _LOGGER.error("Prowl returned: exceeded rate limit")
            raise HomeAssistantError(
                "Prowl service reported: exceeded rate limit"
            ) from ex
        except prowlpy.APIError as ex:
            _LOGGER.error("Unexpected error when calling Prowl API: %s", str(ex))
            raise HomeAssistantError("Unexpected error when calling Prowl API") from ex


class ProwlNotificationEntity(NotifyEntity):
    """Implement the notification service for Prowl.

    This class is used for Prowl config entries.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        api_key: str,
        httpx_client: httpx.AsyncClient,
    ) -> None:
        """Initialize the service."""
        self._hass = hass
        self._prowl = prowlpy.AsyncProwl(api_key, client=httpx_client)
        self._attr_name = name
        self._attr_unique_id = name

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send the message."""
        _LOGGER.debug("Sending Prowl notification from entity %s", self.name)
        try:
            async with asyncio.timeout(10):
                await self._prowl.post(
                    application="Home-Assistant",
                    event=title or ATTR_TITLE_DEFAULT,
                    description=message,
                    priority=0,
                    url=None,
                )
        except TimeoutError as ex:
            _LOGGER.error("Timeout accessing Prowl API")
            raise HomeAssistantError("Timeout accessing Prowl API") from ex
        except prowlpy.InvalidAPIKeyError as ex:
            _LOGGER.error("Invalid API key for Prowl service")
            raise HomeAssistantError("Invalid API key for Prowl service") from ex
        except prowlpy.RateLimitExceededError as ex:
            _LOGGER.error("Prowl returned: exceeded rate limit")
            raise HomeAssistantError(
                "Prowl service reported: exceeded rate limit"
            ) from ex
        except prowlpy.APIError as ex:
            _LOGGER.error("Unexpected error when calling Prowl API: %s", str(ex))
            raise HomeAssistantError("Unexpected error when calling Prowl API") from ex
