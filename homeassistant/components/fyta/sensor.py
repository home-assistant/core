"""Summary data from Fyta."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from fyta_cli.fyta_connector import PLANT_MEASUREMENT_STATUS, PLANT_STATUS

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FytaCoordinator
from .entity import FytaPlantEntity


@dataclass(frozen=True)
class FytaSensorEntityDescription(SensorEntityDescription):
    """Describes Fyta sensor entity."""

    value_fn: Callable[[str | int | float | datetime], str | int | float | datetime] = (
        lambda value: value
    )


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
    ),
    FytaSensorEntityDescription(
        key="status",
        translation_key="plant_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANT_STATUS_LIST,
        value_fn=PLANT_STATUS.get,
    ),
    FytaSensorEntityDescription(
        key="temperature_status",
        translation_key="temperature_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANT_MEASUREMENT_STATUS_LIST,
        value_fn=PLANT_MEASUREMENT_STATUS.get,
    ),
    FytaSensorEntityDescription(
        key="light_status",
        translation_key="light_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANT_MEASUREMENT_STATUS_LIST,
        value_fn=PLANT_MEASUREMENT_STATUS.get,
    ),
    FytaSensorEntityDescription(
        key="moisture_status",
        translation_key="moisture_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANT_MEASUREMENT_STATUS_LIST,
        value_fn=PLANT_MEASUREMENT_STATUS.get,
    ),
    FytaSensorEntityDescription(
        key="salinity_status",
        translation_key="salinity_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANT_MEASUREMENT_STATUS_LIST,
        value_fn=PLANT_MEASUREMENT_STATUS.get,
    ),
    FytaSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FytaSensorEntityDescription(
        key="light",
        translation_key="light",
        native_unit_of_measurement="mol/d",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FytaSensorEntityDescription(
        key="moisture",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.MOISTURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FytaSensorEntityDescription(
        key="salinity",
        translation_key="salinity",
        native_unit_of_measurement="mS/cm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FytaSensorEntityDescription(
        key="ph",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FytaSensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FYTA sensors."""
    coordinator: FytaCoordinator = hass.data[DOMAIN][entry.entry_id]

    plant_entities = [
        FytaPlantSensor(coordinator, entry, sensor, plant_id)
        for plant_id in coordinator.fyta.plant_list
        for sensor in SENSORS
        if sensor.key in coordinator.data[plant_id]
    ]

    async_add_entities(plant_entities)


class FytaPlantSensor(FytaPlantEntity, SensorEntity):
    """Represents a Fyta sensor."""

    entity_description: FytaSensorEntityDescription

    @property
    def native_value(self) -> str | int | float | datetime:
        """Return the state for this sensor."""

        val = self.plant[self.entity_description.key]
        return self.entity_description.value_fn(val)
