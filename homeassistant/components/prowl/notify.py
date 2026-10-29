"""Prowl notification service."""

import asyncio
import logging
from typing import Any, override

import httpx2
import probatio
import prowlpy

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    DOMAIN as NOTIFY_DOMAIN,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
    NotifyEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ENTRY,
    CONF_LEGACY_SERVICE_NAME,
    CONF_SETUP,
    DATA_LEGACY_SETUPS,
    DOMAIN,
    PRIORITY_MAP,
)
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
    if discovery_info is None:
        # YAML keeps providing the legacy service while it is present
        return ProwlNotificationService(
            hass, config[CONF_API_KEY], get_async_client(hass)
        )

    entry: ConfigEntry = discovery_info[CONF_ENTRY]
    service = ProwlNotificationService(
        hass,
        entry.data[CONF_API_KEY],
        get_async_client(hass),
        (entry.entry_id, discovery_info[CONF_SETUP]),
    )
    entry.async_on_unload(service.async_unregister_services)
    return service


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notify entities."""
    # A title composed of several YAML names is not used as entity name
    name = "Prowl" if CONF_LEGACY_SERVICE_NAME in entry.data else entry.title
    # Imported titles can collide (YAML without a name is titled like UI entries);
    # entries set up in the UI keep their existing unique ID
    unique_id = entry.entry_id if entry.source == SOURCE_IMPORT else entry.title
    prowl = ProwlNotificationEntity(
        hass, name, unique_id, entry.data[CONF_API_KEY], get_async_client(hass)
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
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="api_timeout"
        ) from ex
    except prowlpy.APIError as ex:
        if str(ex).startswith("Invalid API key"):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_api_key"
            ) from ex
        if str(ex).startswith("Not accepted"):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="rate_limit_exceeded"
            ) from ex
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="api_error",
            translation_placeholders={"error": str(ex)},
        ) from ex


class ProwlNotificationService(BaseNotificationService):
    """Implement the notification service for Prowl.

    This class is used for legacy configuration via configuration.yaml
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        httpx_client: httpx2.AsyncClient,
        legacy_setup: tuple[str, object] | None = None,
    ) -> None:
        """Initialize the service."""
        self._hass = hass
        self._prowl = prowlpy.AsyncProwl(api_key, client=httpx_client)
        # Entry ID and setup of an entry-backed legacy service
        self._legacy_setup = legacy_setup
        self._owns_service = False

    @override
    async def async_register_services(self) -> None:
        """Register the legacy action for a current setup if the name is free."""
        # The notify loader sets the service up in its own task, so the entry
        # can unload or reload before registration
        if self._legacy_setup is not None:
            entry_id, setup = self._legacy_setup
            if self.hass.data.get(DATA_LEGACY_SETUPS, {}).get(entry_id) is not setup:
                return
        if self.hass.services.has_service(NOTIFY_DOMAIN, self._service_name):
            return
        await super().async_register_services()
        self._owns_service = True

    @override
    async def async_unregister_services(self) -> None:
        """Unregister the legacy action only if this service registered it."""
        if not self._owns_service:
            return
        self._owns_service = False
        await super().async_unregister_services()

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
        unique_id: str,
        api_key: str,
        httpx_client: httpx2.AsyncClient,
    ) -> None:
        """Initialize the service."""
        self._hass = hass
        self._prowl = prowlpy.AsyncProwl(api_key, client=httpx_client)
        self._attr_name = name
        self._attr_unique_id = unique_id

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send the message via the notify.send_message action."""
        await self._async_send(message, title)

    async def prowl_send_message(
        self,
        message: str,
        priority: str,
        title: str | None = None,
        url: str | None = None,
    ) -> None:
        """Send the message via the prowl.send_message action."""
        await self._async_send(message, title, PRIORITY_MAP[priority], url)
        self._async_record_notification()

    async def _async_send(
        self,
        message: str,
        title: str | None,
        priority: int = 0,
        url: str | None = None,
    ) -> None:
        """Post a notification from this entity."""
        _LOGGER.debug("Sending Prowl notification from entity %s", self.name)
        await _async_post(
            self._prowl, title or ATTR_TITLE_DEFAULT, message, priority, url
        )
