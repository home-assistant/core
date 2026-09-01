"""The Chef iQ integration."""

import logging

from chefiq_ble import ChefIqBluetoothDeviceData

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type ChefIqConfigEntry = ConfigEntry[PassiveBluetoothProcessorCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ChefIqConfigEntry) -> bool:
    """Set up Chef iQ BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    data = ChefIqBluetoothDeviceData()

    coordinator = entry.runtime_data = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=data.update,
        # The probe is broadcast-only; all data comes from advertisements and it
        # is never connected to.
        connectable=False,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ChefIqConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
