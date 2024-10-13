"""Support for APCUPSd via its Network Information Server (NIS)."""

from __future__ import annotations

from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .coordinator import APCUPSdCoordinator

type APCUPSdConfigEntry = ConfigEntry[APCUPSdCoordinator]

PLATFORMS: Final = (Platform.BINARY_SENSOR, Platform.SENSOR)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: APCUPSdConfigEntry
) -> bool:
    """Use config values to set up a function enabling status retrieval."""
    host, port = config_entry.data[CONF_HOST], config_entry.data[CONF_PORT]
    coordinator = APCUPSdCoordinator(hass, host, port)

    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator for later uses.
    config_entry.runtime_data = coordinator

    # Forward the config entries to the supported platforms.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: APCUPSdConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
