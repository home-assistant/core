"""The Govee Bluetooth integration."""
from __future__ import annotations

import logging

from bluetooth_sensor_state_data import SensorUpdate
from govee_ble import GoveeBluetoothDeviceData
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import DeviceKey

from homeassistant.components.bluetooth.update_coordinator import (
    BluetoothDataUpdate,
    BluetoothDataUpdateCoordinator,
    BluetoothEntityKey,
)
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MODEL, ATTR_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


class GoveeDataUpdateCoordinator(BluetoothDataUpdateCoordinator[StateType]):
    """Coordinator for Govee Bluetooth data."""


def device_key_to_bluetooth_entity_key(device_key: DeviceKey) -> BluetoothEntityKey:
    """Convert a device key to an entity key."""
    return BluetoothEntityKey(device_key.key, device_key.device_id)


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> BluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return BluetoothDataUpdate(
        devices={
            device_id: DeviceInfo(
                name=device_data[ATTR_NAME], model=device_data[ATTR_MODEL]
            )
            for device_id, device_data in sensor_update.devices.items()
        },
        entity_descriptions={
            device_key_to_bluetooth_entity_key(device_key): SensorEntityDescription(
                key=f"{device_key.key}_{device_key.device_id}",
                name=sensor_description.name,
                device_class=sensor_description.device_class,
                native_unit_of_measurement=sensor_description.native_unit_of_measurement,
            )
            for device_key, sensor_description in sensor_update.entity_descriptions.items()
        },
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee Bluetooth from a config entry."""
    address = entry.unique_id
    assert address is not None

    govee_data = GoveeBluetoothDeviceData()

    @callback
    def _async_update_data(service_info: BluetoothServiceInfo) -> BluetoothDataUpdate:
        """Update data from Govee Bluetooth."""
        return sensor_update_to_bluetooth_data_update(
            govee_data.generate_update(service_info)
        )

    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = GoveeDataUpdateCoordinator(
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
