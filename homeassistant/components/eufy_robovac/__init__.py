"""Support for Eufy RoboVac devices."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_LOCAL_KEY,
    CONF_PROTOCOL_VERSION,
    DEFAULT_PROTOCOL_VERSION,
    PLATFORMS,
    EufyRoboVacConfigEntry,
    EufyRoboVacRuntimeData,
)
from .local_api import EufyRoboVacLocalApi, EufyRoboVacLocalApiError


async def async_setup_entry(hass: HomeAssistant, entry: EufyRoboVacConfigEntry) -> bool:
    """Set up Eufy RoboVac from a config entry."""
    api = EufyRoboVacLocalApi(
        host=entry.data[CONF_HOST],
        device_id=entry.data[CONF_ID],
        local_key=entry.data[CONF_LOCAL_KEY],
        protocol_version=entry.data.get(
            CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION
        ),
    )
    try:
        dps = await api.async_get_dps(hass)
    except EufyRoboVacLocalApiError as err:
        raise ConfigEntryNotReady(
            f"Unable to reach RoboVac {entry.data[CONF_ID]} during setup"
        ) from err

    if not dps:
        raise ConfigEntryNotReady(
            f"RoboVac {entry.data[CONF_ID]} returned no DPS payload during setup"
        )

    runtime_data: EufyRoboVacRuntimeData = {"dps": dps}
    entry.runtime_data = runtime_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EufyRoboVacConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.runtime_data:
        entry.runtime_data["dps"] = {}
    return unload_ok
