"""The Flukso integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DEVICE_HASH, DOMAIN, PLATFORMS
from .discovery import async_discover_device


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Flukso integration."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flukso from a config entry."""
    for _, data in hass.data[DOMAIN].items():
        if entry.data[CONF_DEVICE_HASH] == data[CONF_DEVICE_HASH]:
            return False

    hass.data[DOMAIN][entry.entry_id] = {CONF_DEVICE_HASH: entry.data[CONF_DEVICE_HASH]}

    await async_discover_device(hass, entry)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Flukso config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.data[CONF_DEVICE_HASH])}
    )

    if device is not None:
        device_registry.async_remove_device(device.id)

    return unload_ok
