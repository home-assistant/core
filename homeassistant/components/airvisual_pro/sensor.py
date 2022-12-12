"""Support for AirVisual Pro sensors."""
from __future__ import annotations

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
    TEMP_CELSIUS,
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

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_KIND_AQI,
        name="Air quality index",
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement="AQI",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_KIND_BATTERY_LEVEL,
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key=SENSOR_KIND_CO2,
        name="C02",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_KIND_HUMIDITY,
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key=SENSOR_KIND_PM_0_1,
        name="PM 0.1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_KIND_PM_1_0,
        name="PM 1.0",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_KIND_PM_2_5,
        name="PM 2.5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_KIND_TEMPERATURE,
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_KIND_VOC,
        name="VOC",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
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

    MEASUREMENTS_KEY_TO_VALUE = {
        SENSOR_KIND_CO2: "co2",
        SENSOR_KIND_HUMIDITY: "humidity",
        SENSOR_KIND_PM_0_1: "pm0_1",
        SENSOR_KIND_PM_1_0: "pm1_0",
        SENSOR_KIND_PM_2_5: "pm2_5",
        SENSOR_KIND_TEMPERATURE: "temperature_C",
        SENSOR_KIND_VOC: "voc",
    }

    @property
    def measurements(self) -> dict[str, Any]:
        """Define measurements data."""
        return self.coordinator.data["measurements"]

    @property
    def settings(self) -> dict[str, Any]:
        """Define settings data."""
        return self.coordinator.data["settings"]

    @property
    def status(self) -> dict[str, Any]:
        """Define status data."""
        return self.coordinator.data["status"]

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        if self.entity_description.key == SENSOR_KIND_AQI:
            locale = async_get_aqi_locale(self.settings)
            self._attr_native_value = self.measurements[locale]
        elif self.entity_description.key == SENSOR_KIND_BATTERY_LEVEL:
            self._attr_native_value = self.status["battery"]
        else:
            self._attr_native_value = self.MEASUREMENTS_KEY_TO_VALUE[
                self.entity_description.key
            ]
