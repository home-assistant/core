"""Support for Kegtron sensors."""

from __future__ import annotations

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
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .const import DOMAIN
from .device import device_key_to_bluetooth_entity_key

SENSOR_DESCRIPTIONS = {
    KegtronSensorDeviceClass.PORT_COUNT: SensorEntityDescription(
        key=KegtronSensorDeviceClass.PORT_COUNT,
        icon="mdi:water-pump",
    ),
    KegtronSensorDeviceClass.KEG_SIZE: SensorEntityDescription(
        key=KegtronSensorDeviceClass.KEG_SIZE,
        icon="mdi:keg",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
    ),
    KegtronSensorDeviceClass.KEG_TYPE: SensorEntityDescription(
        key=KegtronSensorDeviceClass.KEG_TYPE,
        icon="mdi:keg",
    ),
    KegtronSensorDeviceClass.VOLUME_START: SensorEntityDescription(
        key=KegtronSensorDeviceClass.VOLUME_START,
        icon="mdi:keg",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
    ),
    KegtronSensorDeviceClass.VOLUME_DISPENSED: SensorEntityDescription(
        key=KegtronSensorDeviceClass.VOLUME_DISPENSED,
        icon="mdi:keg",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL,
    ),
    KegtronSensorDeviceClass.PORT_STATE: SensorEntityDescription(
        key=KegtronSensorDeviceClass.PORT_STATE,
        icon="mdi:water-pump",
    ),
    KegtronSensorDeviceClass.PORT_NAME: SensorEntityDescription(
        key=KegtronSensorDeviceClass.PORT_NAME,
        icon="mdi:water-pump",
    ),
    KegtronSensorDeviceClass.SIGNAL_STRENGTH: SensorEntityDescription(
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
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
                description.device_class
            ]
            for device_key, description in sensor_update.entity_descriptions.items()
            if description.device_class
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
    PassiveBluetoothProcessorEntity[PassiveBluetoothDataProcessor[float | int | None]],
    SensorEntity,
):
    """Representation of a Kegtron sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
