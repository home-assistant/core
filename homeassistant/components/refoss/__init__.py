"""Refoss devices platform loader."""
from __future__ import annotations

from typing import Final

from refoss_ha.device_manager import async_build_base_device
from refoss_ha.exceptions import RefossHttpRequestFail
from refoss_ha.http_device import DeviceInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .models import HomeAssistantRefossData

PLATFORMS: Final = [
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup  entry."""
    hass.data.setdefault(DOMAIN, {})
    device_info = DeviceInfo.from_dict(entry.data)

    try:
        base_device = await async_build_base_device(device_info=device_info)
    except RefossHttpRequestFail as e:
        raise ConfigEntryNotReady from e

    hass.data[DOMAIN][entry.entry_id] = HomeAssistantRefossData(
        base_device=base_device,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the refoss platforms."""
    unload = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload
