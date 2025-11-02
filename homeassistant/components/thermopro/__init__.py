"""The ThermoPro Bluetooth integration."""

from __future__ import annotations

from functools import partial
import logging

from thermopro_ble import SensorUpdate, ThermoProBluetoothDeviceData

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, SIGNAL_DATA_UPDATED

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type ThermoProConfigEntry = ConfigEntry[PassiveBluetoothProcessorCoordinator]


def process_service_info(
    hass: HomeAssistant,
    entry: ConfigEntry,
    data: ThermoProBluetoothDeviceData,
    service_info: BluetoothServiceInfoBleak,
) -> SensorUpdate:
    """Process a BluetoothServiceInfoBleak, running side effects and returning sensor data."""
    update = data.update(service_info)
    async_dispatcher_send(
        hass, f"{SIGNAL_DATA_UPDATED}_{entry.entry_id}", data, service_info, update
    )
    return update


async def async_setup_entry(hass: HomeAssistant, entry: ThermoProConfigEntry) -> bool:
    """Set up ThermoPro BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    data = ThermoProBluetoothDeviceData()
    coordinator = entry.runtime_data = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        update_method=partial(process_service_info, hass, entry, data),
        connectable=False,
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
