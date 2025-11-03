"""The ThermoPro Bluetooth integration."""

from __future__ import annotations

import logging

from thermopro_ble import ThermoProBluetoothDeviceData

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import ThermoProBluetoothProcessorCoordinator, ThermoProConfigEntry

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ThermoProConfigEntry) -> bool:
    """Set up ThermoPro BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    if not (
        bluetooth.async_scanner_count(hass, connectable=False)
        or bluetooth.async_scanner_count(hass, connectable=True)
    ):
        raise ConfigEntryNotReady("Bluetooth scanners not ready")

    coordinator = entry.runtime_data = ThermoProBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        device_data=ThermoProBluetoothDeviceData(),
        entry=entry,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # The coordinator automatically handles device availability changes.
    # When a device becomes unavailable, entities will reflect that state.
    # When the device reappears and broadcasts again, the coordinator will
    # automatically start receiving updates and mark entities as available.
    # Entity data is persisted to storage and restored on restart, so entities
    # will show their last known values even if the device hasn't broadcast yet.
    # This self-healing behavior is built into PassiveBluetoothProcessorCoordinator.
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThermoProConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
