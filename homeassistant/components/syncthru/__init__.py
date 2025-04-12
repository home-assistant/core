"""The syncthru component."""

from __future__ import annotations

from pysyncthru import ConnectionMode, SyncThru, SyncThruAPINotSupported

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import SyncthruCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""

    coordinator = SyncthruCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    if isinstance(coordinator.last_exception, SyncThruAPINotSupported):
        # this means that the printer does not support the syncthru JSON API
        # and the config should simply be discarded
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if config_entry.minor_version == 1:
        syncthru = SyncThru(
            config_entry.data[CONF_URL],
            async_get_clientsession(hass),
            connection_mode=ConnectionMode.API,
        )
        await syncthru.update()
        if syncthru.is_unknown_state():
            return False
        hass.config_entries.async_update_entry(
            config_entry, minor_version=2, unique_id=syncthru.serial_number()
        )

    return True
