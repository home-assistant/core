"""The Flexit Nordic (BACnet) integration."""
from __future__ import annotations

from flexit_bacnet import FlexitBACnet

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flexit Nordic (BACnet) from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    device = FlexitBACnet(entry.data["address"], entry.data["device_id"])

    is_valid = await hass.async_add_executor_job(device.is_valid)
    if not is_valid:
        return False

    hass.data[DOMAIN][entry.entry_id] = device

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
