"""Support for Xiaomi WalkingPad treadmill."""
from __future__ import annotations

from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_CONN_TYPE, CONF_DEFAULT_SPEED, DEFAULT_SPEED, DOMAIN
from .models import WalkingPadBLEDevice, WalkingPadWiFiDevice

PARALLEL_UPDATES: Final = 1

PLATFORMS: Final = [Platform.REMOTE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WalkingPad device from a config entry."""
    device = (
        WalkingPadBLEDevice(hass, entry)
        if entry.data[CONF_CONN_TYPE] == "ble"
        else WalkingPadWiFiDevice(hass, entry)
    )

    await device.async_setup()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle options update."""
        device._default_speed = entry.options.get(CONF_DEFAULT_SPEED, DEFAULT_SPEED)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True
