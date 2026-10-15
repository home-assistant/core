"""Support for APCUPSd via its Network Information Server (NIS)."""

from typing import Final

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .coordinator import APCUPSdConfigEntry, APCUPSdCoordinator

PLATFORMS: Final = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: APCUPSdConfigEntry
) -> None:
    """Use config values to set up a function enabling status retrieval."""
    host, port = config_entry.data[CONF_HOST], config_entry.data[CONF_PORT]
    coordinator = APCUPSdCoordinator(hass, config_entry, host, port)

    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator for later uses.
    config_entry.runtime_data = coordinator

    # Forward the config entries to the supported platforms.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: APCUPSdConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
