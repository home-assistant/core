"""The Govee Bluetooth BLE integration."""

from __future__ import annotations

import logging

from govee_ble import GoveeBluetoothDeviceData, SensorUpdate

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

GoveeBLEConfigEntry = ConfigEntry[PassiveBluetoothProcessorCoordinator[SensorUpdate]]


async def async_setup_entry(hass: HomeAssistant, entry: GoveeBLEConfigEntry) -> bool:
    """Set up Govee BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    data = GoveeBluetoothDeviceData()
    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        update_method=data.update,
    )
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GoveeBLEConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
