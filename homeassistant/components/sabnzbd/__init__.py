"""Support for monitoring an SABnzbd NZB client."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
import homeassistant.helpers.issue_registry as ir

from .const import (
    ATTR_API_KEY,
    ATTR_SPEED,
    DEFAULT_SPEED_LIMIT,
    DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RESUME,
    SERVICE_SET_SPEED,
)
from .coordinator import SabnzbdUpdateCoordinator
from .sab import get_client

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]
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


@callback
def async_get_entry_id_for_service_call(hass: HomeAssistant, call: ServiceCall) -> str:
    """Get the entry ID related to a service call (by device ID)."""
    call_data_api_key = call.data[ATTR_API_KEY]

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[ATTR_API_KEY] == call_data_api_key:
            return entry.entry_id

    raise ValueError(f"No api for API key: {call_data_api_key}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SabNzbd Component."""

    sab_api = await get_client(hass, entry.data)
    if not sab_api:
        raise ConfigEntryNotReady

    coordinator = SabnzbdUpdateCoordinator(hass, entry, sab_api)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    @callback
    def extract_api(
        func: Callable[
            [ServiceCall, SabnzbdUpdateCoordinator], Coroutine[Any, Any, None]
        ],
    ) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
        """Define a decorator to get the correct api for a service call."""

        async def wrapper(call: ServiceCall) -> None:
            """Wrap the service function."""
            entry_id = async_get_entry_id_for_service_call(hass, call)
            coordinator: SabnzbdUpdateCoordinator = hass.data[DOMAIN][entry_id]

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
        speed = call.data.get(ATTR_SPEED)
        await coordinator.sab_api.set_speed_limit(speed)

    for service, method, schema in (
        (SERVICE_PAUSE, async_pause_queue, SERVICE_BASE_SCHEMA),
        (SERVICE_RESUME, async_resume_queue, SERVICE_BASE_SCHEMA),
        (SERVICE_SET_SPEED, async_set_queue_speed, SERVICE_SPEED_SCHEMA),
    ):
        if hass.services.has_service(DOMAIN, service):
            continue

        hass.services.async_register(DOMAIN, service, method, schema=schema)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Sabnzbd config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        # If this is the last loaded instance of Sabnzbd, deregister any services
        # defined during integration setup:
        for service_name in SERVICES:
            hass.services.async_remove(DOMAIN, service_name)

    return unload_ok
