"""The SensorPush Bluetooth integration."""
from __future__ import annotations

import logging

from homeassistant.components.bluetooth.update_coordinator import (
    BluetoothDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .data import SensorPushBluetoothDeviceData

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SensorPush BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None

    # Setup platforms before the coordinator so the
    # entities can be created as soon as we subscribe
    # to miss any data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    coordinator = BluetoothDataUpdateCoordinator(
        hass,
        _LOGGER,
        data=SensorPushBluetoothDeviceData(),
        name=entry.title,
        address=address,
    )
    entry.async_on_unload(coordinator.async_setup())
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
