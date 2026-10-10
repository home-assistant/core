"""Zerproc lights integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DATA_ADDRESSES, DATA_DISCOVERY_SUBSCRIPTION

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zerproc from a config entry."""
    if DATA_ADDRESSES not in hass.data:
        hass.data[DATA_ADDRESSES] = set()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Stop discovery
    unregister_discovery = hass.data.pop(DATA_DISCOVERY_SUBSCRIPTION, None)
    if unregister_discovery:
        unregister_discovery()

    hass.data.pop(DATA_ADDRESSES, None)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
