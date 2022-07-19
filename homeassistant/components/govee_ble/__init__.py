"""The Govee Bluetooth integration."""
from __future__ import annotations

import logging

from bluetooth_sensor_state_data import SensorUpdate
from govee_ble import GoveeBluetoothDeviceData
from home_assistant_bluetooth import BluetoothServiceInfo

from homeassistant.components.bluetooth.update_coordinator import (
    BluetoothDataUpdate,
    BluetoothDataUpdateCoordinator,
    BluetoothEntityKey,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


def sensor_update_to_hass(sensor_update: SensorUpdate) -> BluetoothDataUpdate:
    """Convert a sensor update to a hass data update."""
    return BluetoothDataUpdate({}, {})
    # return BluetoothDataUpdate(
    #    devices={
    #        device_id: DeviceInfo(
    #            name=device_name,
    #            identifiers=identifiers,
    #            manufacturer=manufacturer,
    #            model=model,
    #            sw_version=sw_version,
    #        )
    #        for device_id, (
    #            device_name,
    #            identifiers,
    #            manufacturer,
    #            model,
    #            sw_version,
    #        ) in sensor_update.devices.items()
    #    },
    #    entities={
    #        BluetoothEntityKey(key=key, device_id=device_id): value
    #        for device_id, device_data in sensor_update.devices.items()
    #        for key, value in device_data.entities.items()
    #    },
    #


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee Bluetooth from a config entry."""
    address = entry.unique_id
    assert address is not None

    govee_data = GoveeBluetoothDeviceData()

    @callback
    def _async_update_data(service_info: BluetoothServiceInfo) -> BluetoothDataUpdate:
        """Update data from Govee Bluetooth."""
        return sensor_update_to_hass(govee_data.generate_update(service_info))

    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = BluetoothDataUpdateCoordinator(
        hass,
        _LOGGER,
        update_method=_async_update_data,
        address=address,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_setup())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
