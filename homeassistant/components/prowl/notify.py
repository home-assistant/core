"""Prowl notification service."""

import asyncio
import logging
from typing import Any, override

import httpx
import probatio
import prowlpy

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
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import PRIORITY_MAP
from .issue import async_deprecated_notify_action_call

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {probatio.Required(probatio.Secret(CONF_API_KEY)): cv.string}
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> ProwlNotificationService:
    """Get the Prowl notification service."""
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


async def _async_post(
    prowl: prowlpy.AsyncProwl,
    event: str,
    description: str,
    priority: int = 0,
    url: str | None = None,
) -> None:
    """Post a notification to the Prowl API."""
    try:
        async with asyncio.timeout(10):
            await prowl.post(
                application="Home-Assistant",
                event=event,
                description=description,
                priority=priority,
                url=url,
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

    @override
    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send the message to the user."""
        async_deprecated_notify_action_call(self._hass, self._service_name)

        data = kwargs.get(ATTR_DATA) or {}
        await _async_post(
            self._prowl,
            kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
            message,
            data.get("priority", 0),
            data.get("url"),
        )


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

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send the message via the notify.send_message action."""
        _LOGGER.debug("Sending Prowl notification from entity %s", self.name)
        await _async_post(self._prowl, title or ATTR_TITLE_DEFAULT, message)

    async def prowl_send_message(
        self,
        message: str,
        title: str | None = None,
        priority: str | None = None,
        url: str | None = None,
    ) -> None:
        """Send the message via the prowl.send_message action."""
        _LOGGER.debug("Sending Prowl notification from entity %s", self.name)
        await _async_post(
            self._prowl,
            title or ATTR_TITLE_DEFAULT,
            message,
            PRIORITY_MAP[priority] if priority else 0,
            url,
        )
        self._async_record_notification()
