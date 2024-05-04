"""Support for Qingping binary sensors."""

from __future__ import annotations

from qingping_ble import (
    BinarySensorDeviceClass as QingpingBinarySensorDeviceClass,
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
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .const import DOMAIN
from .device import device_key_to_bluetooth_entity_key

BINARY_SENSOR_DESCRIPTIONS = {
    QingpingBinarySensorDeviceClass.MOTION: BinarySensorEntityDescription(
        key=QingpingBinarySensorDeviceClass.MOTION,
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    QingpingBinarySensorDeviceClass.LIGHT: BinarySensorEntityDescription(
        key=QingpingBinarySensorDeviceClass.LIGHT,
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
    QingpingBinarySensorDeviceClass.DOOR: BinarySensorEntityDescription(
        key=QingpingBinarySensorDeviceClass.DOOR,
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    QingpingBinarySensorDeviceClass.PROBLEM: BinarySensorEntityDescription(
        key=QingpingBinarySensorDeviceClass.PROBLEM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
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
    """Set up the Qingping BLE sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            QingpingBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, BinarySensorEntityDescription)
    )


class QingpingBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[PassiveBluetoothDataProcessor[bool | None]],
    BinarySensorEntity,
):
    """Representation of a Qingping binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
