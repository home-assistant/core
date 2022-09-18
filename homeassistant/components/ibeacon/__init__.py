"""The iBeacon tracker integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get

from .const import DOMAIN
from .coordinator import IBeaconCoordinator

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bluetooth LE Tracker from a config entry."""
    scanner = hass.data[DOMAIN] = IBeaconCoordinator(hass, entry, async_get(hass))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    scanner.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data.pop(DOMAIN)
    return unload_ok
