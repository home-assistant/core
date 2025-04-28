"""The syncthru component."""

from __future__ import annotations

from pysyncthru import ConnectionMode, SyncThru, SyncThruAPINotSupported

from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import SyncThruConfigEntry, SyncthruCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SyncThruConfigEntry) -> bool:
    """Set up config entry."""

    coordinator = SyncthruCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    if isinstance(coordinator.last_exception, SyncThruAPINotSupported):
        # this means that the printer does not support the syncthru JSON API
        # and the config should simply be discarded
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SyncThruConfigEntry) -> bool:
    """Unload the config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: SyncThruConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.minor_version == 1:
        syncthru = SyncThru(
            entry.data[CONF_URL],
            async_get_clientsession(hass),
            connection_mode=ConnectionMode.API,
        )
        await syncthru.update()
        if syncthru.is_unknown_state():
            return False
        hass.config_entries.async_update_entry(
            entry, minor_version=2, unique_id=syncthru.serial_number()
        )

    return True
