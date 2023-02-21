"""Support for OralB sensors."""
from __future__ import annotations

from dataclasses import dataclass

from oralb_ble import OralBSensor, SensorUpdate

from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .const import DOMAIN
from .coordinator import (
    OralbActiveBluetoothProcessorCoordinator,
    OralbPassiveBluetoothDataProcessor,
)
from .device import device_key_to_bluetooth_entity_key


@dataclass
class OralBSensorDescriptionMixin:
    """Mixin for required keys."""

    requires_active_connection: bool = False


@dataclass
class OralBSensorDescription(OralBSensorDescriptionMixin, SensorEntityDescription):
    """Describes Oral B sensor entity."""


SENSOR_DESCRIPTIONS: dict[str, OralBSensorDescription] = {
    OralBSensor.TIME: OralBSensorDescription(
        key=OralBSensor.TIME,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    OralBSensor.SECTOR: OralBSensorDescription(
        key=OralBSensor.SECTOR,
    ),
    OralBSensor.NUMBER_OF_SECTORS: OralBSensorDescription(
        key=OralBSensor.NUMBER_OF_SECTORS,
    ),
    OralBSensor.SECTOR_TIMER: OralBSensorDescription(
        key=OralBSensor.SECTOR_TIMER,
        entity_registry_enabled_default=False,
    ),
    OralBSensor.TOOTHBRUSH_STATE: OralBSensorDescription(
        key=OralBSensor.TOOTHBRUSH_STATE
    ),
    OralBSensor.PRESSURE: OralBSensorDescription(key=OralBSensor.PRESSURE),
    OralBSensor.MODE: OralBSensorDescription(
        key=OralBSensor.MODE,
    ),
    OralBSensor.SIGNAL_STRENGTH: OralBSensorDescription(
        key=OralBSensor.SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    OralBSensor.BATTERY_PERCENT: OralBSensorDescription(
        key=OralBSensor.BATTERY_PERCENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        requires_active_connection=True,
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
                device_key.key
            ]
            for device_key in sensor_update.entity_descriptions
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
    """Set up the OralB BLE sensors."""
    coordinator: OralbActiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = OralbPassiveBluetoothDataProcessor(
        sensor_update_to_bluetooth_data_update
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            OralBBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class OralBBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[OralbPassiveBluetoothDataProcessor],
    SensorEntity,
):
    """Representation of a OralB sensor."""

    entity_description: OralBSensorDescription

    @property
    def native_value(self) -> str | int | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)

    async def async_added_to_hass(self) -> None:
        """Add subscription when added to hass."""
        if self.entity_description.requires_active_connection:
            self.async_on_remove(
                self.processor.coordinator.register_active(self.entity_key)
            )
