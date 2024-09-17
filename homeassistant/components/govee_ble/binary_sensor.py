"""Support for govee-ble binary sensors."""

from __future__ import annotations

from govee_ble import (
    BinarySensorDeviceClass as GoveeBLEBinarySensorDeviceClass,
    SensorUpdate,
)
from govee_ble.parser import ERROR

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .coordinator import GoveeBLEPassiveBluetoothDataProcessor
from .device import device_key_to_bluetooth_entity_key

BINARY_SENSOR_DESCRIPTIONS = {
    GoveeBLEBinarySensorDeviceClass.WINDOW: BinarySensorEntityDescription(
        key=GoveeBLEBinarySensorDeviceClass.WINDOW,
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
    GoveeBLEBinarySensorDeviceClass.MOTION: BinarySensorEntityDescription(
        key=GoveeBLEBinarySensorDeviceClass.MOTION,
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    GoveeBLEBinarySensorDeviceClass.OCCUPANCY: BinarySensorEntityDescription(
        key=GoveeBLEBinarySensorDeviceClass.OCCUPANCY,
        device_class=BinarySensorDeviceClass.OCCUPANCY,
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
    """Set up the govee-ble BLE sensors."""
    coordinator = entry.runtime_data
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            GoveeBluetoothBinarySensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, BinarySensorEntityDescription)
    )


class GoveeBluetoothBinarySensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[bool | None, SensorUpdate]
    ],
    BinarySensorEntity,
):
    """Representation of a govee-ble binary sensor."""

    processor: GoveeBLEPassiveBluetoothDataProcessor

    @property
    def available(self) -> bool:
        """Return False if sensor is in error."""
        coordinator = self.processor.coordinator
        return self.processor.entity_data.get(self.entity_key) != ERROR and (
            ((model_info := coordinator.model_info) and model_info.sleepy)
            or super().available
        )

    @property
    def is_on(self) -> bool | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
