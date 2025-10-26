"""Summary data from Fyta."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from fyta_cli.fyta_models import Plant

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfConductivity,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_MAX_ACCEPTABLE,
    CONF_MAX_GOOD,
    CONF_MIN_ACCEPTABLE,
    CONF_MIN_GOOD,
)
from .coordinator import FytaConfigEntry, FytaCoordinator
from .entity import FytaPlantEntity


@dataclass(frozen=True, kw_only=True)
class FytaSensorEntityDescription(SensorEntityDescription):
    """Describes Fyta sensor entity."""

    value_fn: Callable[[Plant], StateType | datetime]


@dataclass(frozen=True, kw_only=True)
class FytaMeasurementSensorEntityDescription(FytaSensorEntityDescription):
    """Describes Fyta sensor entity."""

    attribute_fn: Callable[[Plant], dict[str, float | None]]


PLANT_STATUS_LIST: list[str] = ["deleted", "doing_great", "need_attention", "no_sensor"]
PLANT_MEASUREMENT_STATUS_LIST: list[str] = [
    "no_data",
    "too_low",
    "low",
    "perfect",
    "high",
    "too_high",
]


SENSORS: Final[list[FytaSensorEntityDescription]] = [
    FytaSensorEntityDescription(
        key="scientific_name",
        translation_key="scientific_name",
        value_fn=lambda plant: plant.scientific_name,
    ),
    FytaSensorEntityDescription(
        key="status",
        translation_key="plant_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANT_STATUS_LIST,
        value_fn=lambda plant: plant.status.name.lower(),
    ),
    FytaSensorEntityDescription(
        key="temperature_status",
        translation_key="temperature_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANT_MEASUREMENT_STATUS_LIST,
        value_fn=lambda plant: plant.temperature_status.name.lower(),
    ),
    FytaSensorEntityDescription(
        key="light_status",
        translation_key="light_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANT_MEASUREMENT_STATUS_LIST,
        value_fn=lambda plant: plant.light_status.name.lower(),
    ),
    FytaSensorEntityDescription(
        key="moisture_status",
        translation_key="moisture_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANT_MEASUREMENT_STATUS_LIST,
        value_fn=lambda plant: plant.moisture_status.name.lower(),
    ),
    FytaSensorEntityDescription(
        key="nutrients_status",
        translation_key="nutrients_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANT_MEASUREMENT_STATUS_LIST,
        value_fn=lambda plant: plant.nutrients_status.name.lower(),
    ),
    FytaSensorEntityDescription(
        key="salinity_status",
        translation_key="salinity_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANT_MEASUREMENT_STATUS_LIST,
        value_fn=lambda plant: plant.salinity_status.name.lower(),
    ),
    FytaSensorEntityDescription(
        key="ph",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda plant: plant.ph,
    ),
    FytaSensorEntityDescription(
        key="fertilise_last",
        translation_key="last_fertilised",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda plant: plant.fertilise_last,
    ),
    FytaSensorEntityDescription(
        key="fertilise_next",
        translation_key="next_fertilisation",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda plant: plant.fertilise_next,
    ),
    FytaSensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda plant: plant.battery_level,
    ),
]

MEASUREMENT_SENSORS: Final[list[FytaMeasurementSensorEntityDescription]] = [
    FytaMeasurementSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        attribute_fn=lambda plant: {
            CONF_MAX_ACCEPTABLE: plant.temperature_max_acceptable,
            CONF_MAX_GOOD: plant.temperature_max_good,
            CONF_MIN_ACCEPTABLE: plant.temperature_min_acceptable,
            CONF_MIN_GOOD: plant.temperature_min_good,
        },
        value_fn=lambda plant: plant.temperature,
    ),
    FytaMeasurementSensorEntityDescription(
        key="light",
        translation_key="light",
        native_unit_of_measurement="μmol/s⋅m²",
        state_class=SensorStateClass.MEASUREMENT,
        attribute_fn=lambda plant: {
            CONF_MAX_ACCEPTABLE: plant.light_max_acceptable,
            CONF_MAX_GOOD: plant.light_max_good,
            CONF_MIN_ACCEPTABLE: plant.light_min_acceptable,
            CONF_MIN_GOOD: plant.light_min_good,
        },
        value_fn=lambda plant: plant.light,
    ),
    FytaMeasurementSensorEntityDescription(
        key="moisture",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.MOISTURE,
        state_class=SensorStateClass.MEASUREMENT,
        attribute_fn=lambda plant: {
            CONF_MAX_ACCEPTABLE: plant.moisture_max_acceptable,
            CONF_MAX_GOOD: plant.moisture_max_good,
            CONF_MIN_ACCEPTABLE: plant.moisture_min_acceptable,
            CONF_MIN_GOOD: plant.moisture_min_good,
        },
        value_fn=lambda plant: plant.moisture,
    ),
    FytaMeasurementSensorEntityDescription(
        key="salinity",
        translation_key="salinity",
        native_unit_of_measurement=UnitOfConductivity.MILLISIEMENS_PER_CM,
        device_class=SensorDeviceClass.CONDUCTIVITY,
        state_class=SensorStateClass.MEASUREMENT,
        attribute_fn=lambda plant: {
            CONF_MAX_ACCEPTABLE: plant.salinity_max_acceptable,
            CONF_MAX_GOOD: plant.salinity_max_good,
            CONF_MIN_ACCEPTABLE: plant.salinity_min_acceptable,
            CONF_MIN_GOOD: plant.salinity_min_good,
        },
        value_fn=lambda plant: plant.salinity,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FytaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the FYTA sensors."""
    coordinator: FytaCoordinator = entry.runtime_data

    plant_entities = [
        FytaPlantSensor(coordinator, entry, sensor, plant_id)
        for plant_id in coordinator.fyta.plant_list
        for sensor in SENSORS
        if sensor.key in dir(coordinator.data.get(plant_id))
    ]

    plant_entities.extend(
        FytaPlantMeasurementSensor(coordinator, entry, sensor, plant_id)
        for plant_id in coordinator.fyta.plant_list
        for sensor in MEASUREMENT_SENSORS
        if sensor.key in dir(coordinator.data.get(plant_id))
    )

    async_add_entities(plant_entities)

    def _async_add_new_device(plant_id: int) -> None:
        plant_entities = [
            FytaPlantSensor(coordinator, entry, sensor, plant_id)
            for sensor in SENSORS
            if sensor.key in dir(coordinator.data.get(plant_id))
        ]

        plant_entities.extend(
            FytaPlantMeasurementSensor(coordinator, entry, sensor, plant_id)
            for sensor in MEASUREMENT_SENSORS
            if sensor.key in dir(coordinator.data.get(plant_id))
        )
        async_add_entities(plant_entities)

    coordinator.new_device_callbacks.append(_async_add_new_device)


class FytaPlantSensor(FytaPlantEntity, SensorEntity):
    """Represents a Fyta sensor."""

    entity_description: FytaSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state for this sensor."""

        return self.entity_description.value_fn(self.plant)


class FytaPlantMeasurementSensor(FytaPlantSensor):
    """Represents a Fyta measurement sensor."""

    entity_description: FytaMeasurementSensorEntityDescription

    @property
    def extra_state_attributes(self) -> dict[str, float | None]:
        """Return the device state attributes."""

        return self.entity_description.attribute_fn(self.plant)
