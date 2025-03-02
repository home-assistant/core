"""Support for monitoring an SABnzbd NZB client."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_API_KEY,
    ATTR_SPEED,
    DEFAULT_SPEED_LIMIT,
    DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RESUME,
    SERVICE_SET_SPEED,
)
from .coordinator import SabnzbdConfigEntry, SabnzbdUpdateCoordinator
from .helpers import get_client

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)

SERVICES = (
    SERVICE_PAUSE,
    SERVICE_RESUME,
    SERVICE_SET_SPEED,
)

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_API_KEY): cv.string,
    }
)

SERVICE_SPEED_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED_LIMIT): cv.string,
    }
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@callback
def async_get_entry_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> SabnzbdConfigEntry:
    """Get the entry ID related to a service call (by device ID)."""
    call_data_api_key = call.data[ATTR_API_KEY]

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[ATTR_API_KEY] == call_data_api_key:
            return entry

    raise ValueError(f"No api for API key: {call_data_api_key}")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SabNzbd Component."""

    @callback
    def extract_api(
        func: Callable[
            [ServiceCall, SabnzbdUpdateCoordinator], Coroutine[Any, Any, None]
        ],
    ) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
        """Define a decorator to get the correct api for a service call."""

        async def wrapper(call: ServiceCall) -> None:
            """Wrap the service function."""
            config_entry = async_get_entry_for_service_call(hass, call)
            coordinator = config_entry.runtime_data

            try:
                await func(call, coordinator)
            except Exception as err:
                raise HomeAssistantError(
                    f"Error while executing {func.__name__}: {err}"
                ) from err

        return wrapper

    @extract_api
    async def async_pause_queue(
        call: ServiceCall, coordinator: SabnzbdUpdateCoordinator
    ) -> None:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "pause_action_deprecated",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            breaks_in_ha_version="2025.6",
            translation_key="pause_action_deprecated",
        )
        await coordinator.sab_api.pause_queue()

    @extract_api
    async def async_resume_queue(
        call: ServiceCall, coordinator: SabnzbdUpdateCoordinator
    ) -> None:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "resume_action_deprecated",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            breaks_in_ha_version="2025.6",
            translation_key="resume_action_deprecated",
        )
        await coordinator.sab_api.resume_queue()

    @extract_api
    async def async_set_queue_speed(
        call: ServiceCall, coordinator: SabnzbdUpdateCoordinator
    ) -> None:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "set_speed_action_deprecated",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            breaks_in_ha_version="2025.6",
            translation_key="set_speed_action_deprecated",
        )
        speed = call.data.get(ATTR_SPEED)
        await coordinator.sab_api.set_speed_limit(speed)

    for service, method, schema in (
        (SERVICE_PAUSE, async_pause_queue, SERVICE_BASE_SCHEMA),
        (SERVICE_RESUME, async_resume_queue, SERVICE_BASE_SCHEMA),
        (SERVICE_SET_SPEED, async_set_queue_speed, SERVICE_SPEED_SCHEMA),
    ):
        hass.services.async_register(DOMAIN, service, method, schema=schema)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SabnzbdConfigEntry) -> bool:
    """Set up the SabNzbd Component."""

    sab_api = await get_client(hass, entry.data)
    if not sab_api:
        raise ConfigEntryNotReady

    coordinator = SabnzbdUpdateCoordinator(hass, entry, sab_api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SabnzbdConfigEntry) -> bool:
    """Unload a Sabnzbd config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
