"""Support for the Moehlenhoff Alpha2."""

from __future__ import annotations

from moehlenhoff_alpha2 import Alpha2Base

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .coordinator import Alpha2BaseCoordinator, Alpha2ConfigEntry

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: Alpha2ConfigEntry) -> bool:
    """Set up a config entry."""
    base = Alpha2Base(entry.data[CONF_HOST])
    coordinator = Alpha2BaseCoordinator(hass, entry, base)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Alpha2ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: Alpha2ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
