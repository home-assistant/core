"""Support for Kegtron sensors."""
from __future__ import annotations

from typing import Optional, Union

from kegtron_ble import (
    SensorDeviceClass as KegtronSensorDeviceClass,
    SensorUpdate,
    Units,
)

from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, VOLUME_LITERS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import device_key_to_bluetooth_entity_key, sensor_device_info_to_hass

SENSOR_DESCRIPTIONS = {
    ("keg_size"): SensorEntityDescription(
        key="keg_size",
        icon="mdi:keg",
        native_unit_of_measurement=VOLUME_LITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("keg_type"): SensorEntityDescription(
        key="keg_type",
        icon="mdi:keg",
    ),
    ("volume_start"): SensorEntityDescription(
        key="volume_start",
        icon="mdi:keg",
        native_unit_of_measurement=VOLUME_LITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ("port_count"): SensorEntityDescription(
        key="port_count",
        icon="mdi:keg",
    ),
    ("port_index"): SensorEntityDescription(
        key="port_index",
        icon="mdi:keg",
    ),
    ("port_state"): SensorEntityDescription(
        key="port_state",
        icon="mdi:keg",
    ),
    ("volume_dispensed_port_1"): SensorEntityDescription(
        key="volume_dispensed_port_1",
        icon="mdi:keg",
        native_unit_of_measurement=VOLUME_LITERS,
        state_class=SensorStateClass.TOTAL,
    ),
    ("volume_dispensed_port_2"): SensorEntityDescription(
        key="volume_dispensed_port_2",
        icon="mdi:keg",
        native_unit_of_measurement=VOLUME_LITERS,
        state_class=SensorStateClass.TOTAL,
    ),
    ("signal_strength"): SensorEntityDescription(
        key=f"{KegtronSensorDeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
            device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
                (description.device_key.key)
            ]
            for device_key, description in sensor_update.entity_descriptions.items()
        },
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Kegtron BLE sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            KegtronBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class KegtronBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[Optional[Union[float, int]]]
    ],
    SensorEntity,
):
    """Representation of a Kegtron sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
