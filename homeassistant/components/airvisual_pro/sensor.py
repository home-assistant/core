"""Support for AirVisual Pro sensors."""
from __future__ import annotations

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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import AirVisualProEntity
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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AirVisual sensors based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        AirVisualProSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class AirVisualProSensor(AirVisualProEntity, SensorEntity):
    """Define an AirVisual Pro sensor."""

    _attr_has_entity_name = True

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        if self.entity_description.key == SENSOR_KIND_AQI:
            if self.coordinator.data["settings"]["is_aqi_usa"]:
                self._attr_native_value = self.coordinator.data["measurements"][
                    "aqi_us"
                ]
            else:
                self._attr_native_value = self.coordinator.data["measurements"][
                    "aqi_cn"
                ]
        elif self.entity_description.key == SENSOR_KIND_BATTERY_LEVEL:
            self._attr_native_value = self.coordinator.data["status"]["battery"]
        elif self.entity_description.key == SENSOR_KIND_CO2:
            self._attr_native_value = self.coordinator.data["measurements"].get("co2")
        elif self.entity_description.key == SENSOR_KIND_HUMIDITY:
            self._attr_native_value = self.coordinator.data["measurements"].get(
                "humidity"
            )
        elif self.entity_description.key == SENSOR_KIND_PM_0_1:
            self._attr_native_value = self.coordinator.data["measurements"].get("pm0_1")
        elif self.entity_description.key == SENSOR_KIND_PM_1_0:
            self._attr_native_value = self.coordinator.data["measurements"].get("pm1_0")
        elif self.entity_description.key == SENSOR_KIND_PM_2_5:
            self._attr_native_value = self.coordinator.data["measurements"].get("pm2_5")
        elif self.entity_description.key == SENSOR_KIND_TEMPERATURE:
            self._attr_native_value = self.coordinator.data["measurements"].get(
                "temperature_C"
            )
        elif self.entity_description.key == SENSOR_KIND_VOC:
            self._attr_native_value = self.coordinator.data["measurements"].get("voc")
