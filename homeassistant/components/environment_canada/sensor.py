"""Support for the Environment Canada weather service."""
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
    ATTR_LOCATION,
    DEGREE,
    LENGTH_KILOMETERS,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_KPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    UV_INDEX,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_STATION, DOMAIN

ATTR_TIME = "alert time"


@dataclass
class ECSensorEntityDescription(SensorEntityDescription):
    """Class describing EC sensor entities."""

    value: Callable[[str, Any], Any] | None = None
    transform: Callable[[Any], Any] | None = None


SENSOR_TYPES: tuple[ECSensorEntityDescription, ...] = (
    ECSensorEntityDescription(
        key="condition",
        name="Current Condition",
    ),
    ECSensorEntityDescription(
        key="dewpoint",
        name="Dew Point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="high_temp",
        name="High Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="humidex",
        name="Humidex",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="icon_code",
        name="Icon Code",
    ),
    ECSensorEntityDescription(
        key="low_temp",
        name="Low Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="normal_high",
        name="Normal High Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="normal_low",
        name="Normal Low Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="pop",
        name="Chance of Precipitation",
        native_unit_of_measurement=PERCENTAGE,
    ),
    ECSensorEntityDescription(
        key="precip_yesterday",
        name="Precipitation Yesterday",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="pressure",
        name="Barometric Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_KPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="tendency",
        name="Tendency",
        transform=lambda val: str(val).capitalize(),
    ),
    ECSensorEntityDescription(
        key="text_summary",
        name="Summary",
        transform=lambda val: val[:255],
    ),
    ECSensorEntityDescription(
        key="timestamp",
        name="Observation Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda key, ecdata: ecdata.metadata.get(key),
    ),
    ECSensorEntityDescription(
        key="uv_index",
        name="UV Index",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="visibility",
        name="Visibility",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="wind_bearing",
        name="Wind Bearing",
        native_unit_of_measurement=DEGREE,
    ),
    ECSensorEntityDescription(
        key="wind_chill",
        name="Wind Chill",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="wind_dir",
        name="Wind Direction",
    ),
    ECSensorEntityDescription(
        key="wind_gust",
        name="Wind Gust",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ECSensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

AQHI_SENSOR = ECSensorEntityDescription(
    key="aqhi",
    name="AQHI",
    device_class=SensorDeviceClass.AQI,
    native_unit_of_measurement="AQI",
    state_class=SensorStateClass.MEASUREMENT,
    value=lambda _, ecdata: ecdata.current,
)

ALERT_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="advisories",
        name="Advisory",
        icon="mdi:bell-alert",
    ),
    SensorEntityDescription(
        key="endings",
        name="Endings",
        icon="mdi:alert-circle-check",
    ),
    SensorEntityDescription(
        key="statements",
        name="Statements",
        icon="mdi:bell-alert",
    ),
    SensorEntityDescription(
        key="warnings",
        name="Warnings",
        icon="mdi:alert-octagon",
    ),
    SensorEntityDescription(
        key="watches",
        name="Watches",
        icon="mdi:alert",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["weather_coordinator"]
    sensors: list[ECBaseSensor] = [ECSensor(coordinator, desc) for desc in SENSOR_TYPES]
    sensors.extend([ECAlertSensor(coordinator, desc) for desc in ALERT_TYPES])
    aqhi_coordinator = hass.data[DOMAIN][config_entry.entry_id]["aqhi_coordinator"]
    sensors.append(ECSensor(aqhi_coordinator, AQHI_SENSOR))
    async_add_entities(sensors)


class ECBaseSensor(CoordinatorEntity, SensorEntity):
    """Environment Canada sensor base."""

    def __init__(self, coordinator, description):
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._ec_data = coordinator.ec_data
        self._attr_attribution = self._ec_data.metadata["attribution"]
        self._attr_name = f"{coordinator.config_entry.title} {description.name}"
        self._attr_unique_id = f"{self._ec_data.metadata['location']}-{description.key}"


class ECSensor(ECBaseSensor):
    """Environment Canada sensor for conditions."""

    entity_description: ECSensorEntityDescription

    def __init__(self, coordinator, description):
        """Initialize the sensor."""
        super().__init__(coordinator, description)
        self._attr_extra_state_attributes = {
            ATTR_LOCATION: self._ec_data.metadata.get("location"),
            ATTR_STATION: self._ec_data.metadata.get("station"),
        }

    @property
    def native_value(self):
        """Update current conditions."""
        sensor_type = self.entity_description.key
        if self.entity_description.value:
            value = self.entity_description.value(sensor_type, self._ec_data)
        else:
            value = self._ec_data.conditions.get(sensor_type, {}).get("value")
        if self.entity_description.transform:
            value = self.entity_description.transform(value)
        return value


class ECAlertSensor(ECBaseSensor):
    """Environment Canada sensor for alerts."""

    @property
    def native_value(self):
        """Return the state."""
        alert_name = self.entity_description.key
        value = self._ec_data.alerts.get(alert_name, {}).get("value", [])
        return len(value)

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes."""
        alert_name = self.entity_description.key
        value = self._ec_data.alerts.get(alert_name, {}).get("value", [])

        extra_state_attrs = {
            ATTR_LOCATION: self._ec_data.metadata.get("location"),
            ATTR_STATION: self._ec_data.metadata.get("station"),
        }
        for index, alert in enumerate(value, start=1):
            extra_state_attrs[f"alert_{index}"] = alert.get("title")
            extra_state_attrs[f"alert_time_{index}"] = alert.get("date")

        return extra_state_attrs
