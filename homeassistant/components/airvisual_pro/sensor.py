"""Support for AirVisual Pro sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirVisualProData, AirVisualProEntity
from .const import DOMAIN

SENSOR_KIND_AQI = "air_quality_index"
SENSOR_KIND_BATTERY_LEVEL = "battery_level"
SENSOR_KIND_CO2 = "carbon_dioxide"
SENSOR_KIND_HUMIDITY = "humidity"
SENSOR_KIND_PM_0_1 = "particulate_matter_0_1"
SENSOR_KIND_PM_1_0 = "particulate_matter_1_0"
SENSOR_KIND_PM_2_5 = "particulate_matter_2_5"
SENSOR_KIND_SENSOR_LIFE = "sensor_life"
SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_VOC = "voc"


@dataclass
class AirVisualProMeasurementKeyMixin:
    """Define an entity description mixin to include a measurement key."""

    value_fn: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], float | int]


@dataclass
class AirVisualProMeasurementDescription(
    SensorEntityDescription, AirVisualProMeasurementKeyMixin
):
    """Describe an AirVisual Pro sensor."""


SENSOR_DESCRIPTIONS = (
    AirVisualProMeasurementDescription(
        key=SENSOR_KIND_AQI,
        name="Air quality index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda settings, status, measurements: measurements[
            async_get_aqi_locale(settings)
        ],
    ),
    AirVisualProMeasurementDescription(
        key=SENSOR_KIND_BATTERY_LEVEL,
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda settings, status, measurements: status["battery"],
    ),
    AirVisualProMeasurementDescription(
        key=SENSOR_KIND_CO2,
        name="C02",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda settings, status, measurements: measurements["co2"],
    ),
    AirVisualProMeasurementDescription(
        key=SENSOR_KIND_HUMIDITY,
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda settings, status, measurements: measurements["humidity"],
    ),
    AirVisualProMeasurementDescription(
        key=SENSOR_KIND_PM_0_1,
        name="PM 0.1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda settings, status, measurements: measurements["pm0_1"],
    ),
    AirVisualProMeasurementDescription(
        key=SENSOR_KIND_PM_1_0,
        name="PM 1.0",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda settings, status, measurements: measurements["pm1_0"],
    ),
    AirVisualProMeasurementDescription(
        key=SENSOR_KIND_PM_2_5,
        name="PM 2.5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda settings, status, measurements: measurements["pm2_5"],
    ),
    AirVisualProMeasurementDescription(
        key=SENSOR_KIND_TEMPERATURE,
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda settings, status, measurements: measurements["temperature_C"],
    ),
    AirVisualProMeasurementDescription(
        key=SENSOR_KIND_VOC,
        name="VOC",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda settings, status, measurements: measurements["voc"],
    ),
)


@callback
def async_get_aqi_locale(settings: dict[str, Any]) -> str:
    """Return the correct AQI locale based on settings data."""
    if settings["is_aqi_usa"]:
        return "aqi_us"
    return "aqi_cn"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AirVisual sensors based on a config entry."""
    data: AirVisualProData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        AirVisualProSensor(data.coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class AirVisualProSensor(AirVisualProEntity, SensorEntity):
    """Define an AirVisual Pro sensor."""

    _attr_has_entity_name = True

    entity_description: AirVisualProMeasurementDescription

    @property
    def native_value(self) -> float | int:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.coordinator.data["settings"],
            self.coordinator.data["status"],
            self.coordinator.data["measurements"],
        )
