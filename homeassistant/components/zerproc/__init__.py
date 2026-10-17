"""Zerproc lights integration."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DATA_ADDRESSES, DATA_DISCOVERY_SUBSCRIPTION, DOMAIN

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Zerproc from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if DATA_ADDRESSES not in hass.data[DOMAIN]:
        hass.data[DOMAIN][DATA_ADDRESSES] = set()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    # Stop discovery
    unregister_discovery = hass.data[DOMAIN].pop(DATA_DISCOVERY_SUBSCRIPTION, None)
    if unregister_discovery:
        unregister_discovery()

    hass.data.pop(DOMAIN, None)

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
