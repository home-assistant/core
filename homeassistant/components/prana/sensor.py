"""Sensor platform for Prana integration."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PranaConfigEntry
from .entity import PranaBaseEntity, PranaCoordinator

PARALLEL_UPDATES = 1


class PranaSensorType(StrEnum):
    """Enumerates Prana sensor types exposed by the device API."""

    HUMIDITY = "humidity"
    VOC = "voc"
    AIR_PRESSURE = "air_pressure"
    CO2 = "co2"
    INSIDE_TEMPERATURE = "inside_temperature"
    INSIDE_TEMPERATURE_2 = "inside_temperature_2"
    OUTSIDE_TEMPERATURE = "outside_temperature"
    OUTSIDE_TEMPERATURE_2 = "outside_temperature_2"


@dataclass(frozen=True, kw_only=True)
class PranaSensorEntityDescription(SensorEntityDescription):
    """Description of a Prana sensor entity."""

    key: PranaSensorType
    state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    value_fn: Callable[[PranaCoordinator], StateType | None]


ENTITIES: tuple[PranaSensorEntityDescription, ...] = (
    PranaSensorEntityDescription(
        key=PranaSensorType.HUMIDITY,
        value_fn=lambda coord: coord.data.humidity,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    PranaSensorEntityDescription(
        key=PranaSensorType.VOC,
        value_fn=lambda coord: coord.data.voc,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
    ),
    PranaSensorEntityDescription(
        key=PranaSensorType.AIR_PRESSURE,
        value_fn=lambda coord: coord.data.air_pressure,
        native_unit_of_measurement=UnitOfPressure.MMHG,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    PranaSensorEntityDescription(
        key=PranaSensorType.CO2,
        value_fn=lambda coord: coord.data.co2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
    ),
    PranaSensorEntityDescription(
        key=PranaSensorType.INSIDE_TEMPERATURE,
        translation_key="inside_temperature",
        value_fn=lambda coord: coord.data.inside_temperature,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    PranaSensorEntityDescription(
        key=PranaSensorType.INSIDE_TEMPERATURE_2,
        translation_key="inside_temperature_2",
        value_fn=lambda coord: coord.data.inside_temperature_2,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    PranaSensorEntityDescription(
        key=PranaSensorType.OUTSIDE_TEMPERATURE,
        translation_key="outside_temperature",
        value_fn=lambda coord: coord.data.outside_temperature,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    PranaSensorEntityDescription(
        key=PranaSensorType.OUTSIDE_TEMPERATURE_2,
        translation_key="outside_temperature_2",
        value_fn=lambda coord: coord.data.outside_temperature_2,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PranaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prana sensor entities from a config entry."""
    async_add_entities(
        PranaSensor(entry.runtime_data, description)
        for description in ENTITIES
        if description.value_fn(entry.runtime_data) is not None
    )


class PranaSensor(PranaBaseEntity, SensorEntity):
    """Representation of a Prana sensor entity."""

    entity_description: PranaSensorEntityDescription

    @property
    def native_value(self) -> StateType | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator)
