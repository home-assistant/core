"""The ThermoPro Bluetooth integration."""

from __future__ import annotations

import logging

from thermopro_ble import ThermoProBluetoothDeviceData

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    async_last_service_info,
)
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
    service_info = async_last_service_info(hass, address, connectable=False) or async_last_service_info(hass, address, connectable=True)
    if service_info:
        coordinator.restore_service_info(service_info)
    # Only start after all platforms have had a chance to subscribe.
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThermoProConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
