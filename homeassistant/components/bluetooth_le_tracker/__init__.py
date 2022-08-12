"""The bluetooth_le_tracker component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .data import BLEScanner

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bluetooth LE Tracker from a config entry."""
    scanner = hass.data[DOMAIN] = BLEScanner(hass, entry.options)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    scanner.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        scanner: BLEScanner = hass.data.pop(DOMAIN)
        scanner.async_stop()
    return unload_ok
