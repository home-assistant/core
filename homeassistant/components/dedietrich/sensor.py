"""Support for De Dietrich sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from diematic_modbus import Diematic, DiematicISystem

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import DeDietrichConfigEntry
from .entity import DeDietrichEntity, DeDietrichEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DeDietrichSensorDescription(SensorEntityDescription, DeDietrichEntityDescription):
    """Describe a De Dietrich sensor."""

    value_fn: Callable[[Diematic | DiematicISystem], StateType]


SENSOR_DESCRIPTIONS: tuple[DeDietrichSensorDescription, ...] = (
    DeDietrichSensorDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        component="sensors",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.sensors.outdoor_temp,
    ),
    DeDietrichSensorDescription(
        key="boiler_temperature",
        translation_key="boiler_temperature",
        component="sensors",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.sensors.boiler_temp,
    ),
    DeDietrichSensorDescription(
        key="return_temperature",
        translation_key="return_temperature",
        component="sensors",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.sensors.return_temp,
    ),
    DeDietrichSensorDescription(
        key="exhaust_temperature",
        translation_key="exhaust_temperature",
        component="sensors",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.sensors.smoke_temp,
    ),
    DeDietrichSensorDescription(
        key="water_pressure",
        translation_key="water_pressure",
        component="sensors",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.sensors.water_pressure,
    ),
    DeDietrichSensorDescription(
        key="calc_boiler_temperature",
        translation_key="calc_boiler_temperature",
        component="sensors",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.sensors.calc_boiler_temp,
    ),
    DeDietrichSensorDescription(
        key="fan_speed",
        translation_key="fan_speed",
        component="sensors",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.sensors.fan_speed,
    ),
    DeDietrichSensorDescription(
        key="ionization_current",
        translation_key="ionization_current",
        component="sensors",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MICROAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.sensors.ionization_current,
    ),
    DeDietrichSensorDescription(
        key="hot_water_temperature",
        translation_key="hot_water_temperature",
        component="hot_water",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda device: device.hot_water.temp,
    ),
    DeDietrichSensorDescription(
        key="circuit_a_room_temperature",
        translation_key="circuit_a_room_temperature",
        component="circuit_a",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        exists_fn=lambda device: device.circuit_a_present,
        value_fn=lambda device: device.circuit_a.room_temp,
    ),
    DeDietrichSensorDescription(
        key="circuit_b_room_temperature",
        translation_key="circuit_b_room_temperature",
        component="circuit_b",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        exists_fn=lambda device: device.circuit_b_present,
        value_fn=lambda device: device.circuit_b.room_temp,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeDietrichConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the De Dietrich sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        DeDietrichSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if description.exists_fn(coordinator.device)
    )


class DeDietrichSensor(DeDietrichEntity, SensorEntity):
    """A read-only value off one of the boiler's components."""

    entity_description: DeDietrichSensorDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value this sensor reads from the device."""
        return self.entity_description.value_fn(self.coordinator.device)
