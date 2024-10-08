"""The Wallbox integration."""

from __future__ import annotations

import voluptuous as vol
from wallbox import Wallbox

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    CONF_STATION,
    DOMAIN,
    SERVICE_GET_SESSIONS,
    SESSION_END_DATETIME,
    SESSION_SERIAL,
    SESSION_START_DATETIME,
    UPDATE_INTERVAL,
)
from .coordinator import InvalidAuth, WallboxCoordinator

PLATFORMS = [Platform.LOCK, Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

SERVICE_GET_SESSIONS_SCHEMA = vol.Schema(
    {
        vol.Required(SESSION_SERIAL): cv.string,
        vol.Required(SESSION_START_DATETIME): cv.datetime,
        vol.Required(SESSION_END_DATETIME): cv.datetime,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wallbox from a config entry."""
    wallbox = Wallbox(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        jwtTokenDrift=UPDATE_INTERVAL,
    )
    wallbox_coordinator = WallboxCoordinator(
        entry.data[CONF_STATION],
        wallbox,
        hass,
    )

    try:
        await wallbox_coordinator.async_validate_input()

    except InvalidAuth as ex:
        raise ConfigEntryAuthFailed from ex

    await wallbox_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = wallbox_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_get_sessions_service(service_call: ServiceCall) -> ServiceResponse:
        """Get charging sessions between timestamps for Wallbox."""
        start = service_call.data.get(SESSION_START_DATETIME, dt_util.now())
        end = service_call.data.get(SESSION_END_DATETIME, dt_util.now())
        serial = service_call.data.get(SESSION_SERIAL, "12345")

        return await wallbox_coordinator.async_get_sessions(
            serial, dt_util.as_local(start), dt_util.as_local(end)
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SESSIONS,
        async_get_sessions_service,
        schema=SERVICE_GET_SESSIONS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
