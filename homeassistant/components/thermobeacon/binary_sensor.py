"""Support for ThermoBeacon binary sensors."""
from __future__ import annotations

from typing import Optional

from thermobeacon_ble import (
    BinarySensorDeviceClass as ThermoBeaconBinarySensorDeviceClass,
    SensorUpdate,
)

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import device_key_to_bluetooth_entity_key, sensor_device_info_to_hass

BINARY_SENSOR_DESCRIPTIONS = {
    ThermoBeaconBinarySensorDeviceClass.MOTION: BinarySensorEntityDescription(
        key=ThermoBeaconBinarySensorDeviceClass.MOTION,
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    ThermoBeaconBinarySensorDeviceClass.LIGHT: BinarySensorEntityDescription(
        key=ThermoBeaconBinarySensorDeviceClass.LIGHT,
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
    ThermoBeaconBinarySensorDeviceClass.DOOR: BinarySensorEntityDescription(
        key=ThermoBeaconBinarySensorDeviceClass.DOOR,
        device_class=BinarySensorDeviceClass.DOOR,
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            device_key_to_bluetooth_entity_key(device_key): BINARY_SENSOR_DESCRIPTIONS[
                description.device_class
            ]
            for device_key, description in sensor_update.binary_entity_descriptions.items()
            if description.device_class
        },
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ThermoBeacon BLE sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            ThermoBeaconBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class ThermoBeaconBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[PassiveBluetoothDataProcessor[Optional[bool]]],
    BinarySensorEntity,
):
    """Representation of a ThermoBeacon binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
