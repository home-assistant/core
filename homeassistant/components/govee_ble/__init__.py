"""The Govee Bluetooth integration."""
from __future__ import annotations

import logging

from homeassistant.components.bluetooth.update_coordinator import (
    BluetoothDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .data import GoveeBluetoothDeviceData

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee Bluetooth from a config entry."""
    address = entry.unique_id
    assert address is not None
    coordinator = BluetoothDataUpdateCoordinator(
        hass,
        _LOGGER,
        data=GoveeBluetoothDeviceData(),
        name=entry.title,
        address=address,
    )
    entry.async_on_unload(coordinator.async_setup())
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
