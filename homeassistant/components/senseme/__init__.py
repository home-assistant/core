"""The SenseME integration."""
from __future__ import annotations

from aiosenseme import async_get_device_by_device_info

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_INFO, DOMAIN, PLATFORMS, UPDATE_RATE
from .discovery import async_start_discovery


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SenseME from a config entry."""
    async_start_discovery(hass)

    status, device = await async_get_device_by_device_info(
        info=entry.data[CONF_INFO], start_first=True, refresh_minutes=UPDATE_RATE
    )

    if not status:
        # even if the device could not connect it will keep trying because start_first=True
        device.stop()
        raise ConfigEntryNotReady(f"Connect to address {device.address} failed")

    await device.async_update(not status)

    hass.data[DOMAIN][entry.entry_id] = {CONF_DEVICE: device}
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN][entry.entry_id][CONF_DEVICE].stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
