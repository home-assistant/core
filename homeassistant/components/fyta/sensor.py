"""Summary data from Fyta."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FytaCoordinator, FytaEntity


@dataclass(frozen=True)
class FytaSensorEntityDescription(SensorEntityDescription):
    """Describes Fyta sensor entity."""

    value_fn: Callable[[str | int | float], str | int | float | datetime] = (
        lambda value: value
    )


SENSORS: Final[list[FytaSensorEntityDescription]] = [
    FytaSensorEntityDescription(
        key="plant_name",
        translation_key="fyta_plant_name",
    ),
    FytaSensorEntityDescription(
        key="scientific_name",
        translation_key="fyta_scientific_name",
    ),
    FytaSensorEntityDescription(
        key="plant_status",
        translation_key="fyta_plant_status",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flower",
    ),
    FytaSensorEntityDescription(
        key="temperature_status",
        translation_key="fyta_temperature_status",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-lines",
    ),
    FytaSensorEntityDescription(
        key="light_status",
        translation_key="fyta_light_status",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sun-clock-outline",
    ),
    FytaSensorEntityDescription(
        key="moisture_status",
        translation_key="fyta_moisture_status",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent-alert",
    ),
    FytaSensorEntityDescription(
        key="salinity_status",
        translation_key="fyta_salinity_status",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sprout-outline",
    ),
    FytaSensorEntityDescription(
        key="temperature",
        translation_key="fyta_temperature",
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    FytaSensorEntityDescription(
        key="light",
        translation_key="fyta_light",
        native_unit_of_measurement="mol/d",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-sunny",
    ),
    FytaSensorEntityDescription(
        key="moisture",
        translation_key="fyta_moisture",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.MOISTURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    FytaSensorEntityDescription(
        key="salinity",
        translation_key="fyta_salinity",
        native_unit_of_measurement="mS/cm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sprout-outline",
    ),
    FytaSensorEntityDescription(
        key="ph",
        translation_key="fyta_PH",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ph",
    ),
    FytaSensorEntityDescription(
        key="battery_level",
        translation_key="fyta_battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery",
    ),
    FytaSensorEntityDescription(
        key="last_updated",
        translation_key="fyta_last_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:update",
    ),
    FytaSensorEntityDescription(
        key="plant_number",
        translation_key="fyta_plant_number",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:update",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FYTA binary sensors."""
    coordinator: FytaCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            FytaSensor(coordinator, entry, sensor)
            for sensor in SENSORS
            if sensor.key in coordinator.data
        ]
    )

    for plant_id in coordinator.plant_list:
        async_add_entities(
            [
                FytaSensor(coordinator, entry, sensor, plant_id)
                for sensor in SENSORS
                if sensor.key in coordinator.data[plant_id]
            ]
        )


class FytaSensor(FytaEntity, SensorEntity):
    """Represents a Fyta sensor."""

    entity_description: FytaSensorEntityDescription

    @property
    def native_value(self) -> str | int | float | datetime:
        """Return the state for this sensor."""
        if self.plant_id == -1:
            val = self.coordinator.data[self.entity_description.key]
        else:
            val = self.coordinator.data[self.plant_id][self.entity_description.key]
        return self.entity_description.value_fn(val)
