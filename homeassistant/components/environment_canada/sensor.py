"""Sensors for Environment Canada (EC)."""
from __future__ import annotations

from dataclasses import dataclass
import datetime

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_HPA,
    PRESSURE_INHG,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    UV_INDEX,
)

from . import ECBaseEntity, convert
from .const import DOMAIN

ALERTS = [
    ("advisories", "Advisory", "mdi:bell-alert"),
    ("endings", "Ending", "mdi:alert-circle-check"),
    ("statements", "Statement", "mdi:bell-alert"),
    ("warnings", "Warning", "mdi:alert-octagon"),
    ("watches", "Watch", "mdi:alert"),
]
MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=5)


@dataclass
class ECSensorEntityDescription(SensorEntityDescription):
    """Class describing ECSensor entities."""

    unit_convert: str | None = None


SENSOR_TYPES: tuple[ECSensorEntityDescription, ...] = (
    ECSensorEntityDescription(
        key="dewpoint",
        name="Dew Point",
        icon="mdi:thermometer",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="temperature",
        name="Temperature",
        icon="mdi:thermometer",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="low_temp",
        name="Low Temperature",
        icon="mdi:thermometer-chevron-down",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="high_temp",
        name="High Temperature",
        icon="mdi:thermometer-chevron-up",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="wind_chill",
        name="Wind Chill",
        icon="mdi:thermometer-minus",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="humidex",
        name="Humidex",
        icon="mdi:thermometer-plus",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="humidity",
        name="Humidity",
        icon="mdi:water-percent",
        device_class=DEVICE_CLASS_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        unit_convert=PERCENTAGE,
    ),
    ECSensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        icon="mdi:weather-windy",
        device_class=None,
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        unit_convert=SPEED_MILES_PER_HOUR,
    ),
    ECSensorEntityDescription(
        key="wind_gust",
        name="Wind Gust",
        icon="mdi:weather-windy",
        device_class=None,
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        unit_convert=SPEED_MILES_PER_HOUR,
    ),
    ECSensorEntityDescription(
        key="wind_bearing",
        name="Wind Bearing",
        icon="mdi:compass",
        device_class=None,
        native_unit_of_measurement=DEGREE,
        unit_convert=DEGREE,
    ),
    ECSensorEntityDescription(
        key="pressure",
        name="Barometric Pressure",
        icon="mdi:gauge",
        device_class=DEVICE_CLASS_PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
        unit_convert=PRESSURE_INHG,
    ),
    ECSensorEntityDescription(
        key="visibility",
        name="Visibility",
        icon="mdi:telescope",
        device_class=None,
        native_unit_of_measurement=LENGTH_KILOMETERS,
        unit_convert=LENGTH_MILES,
    ),
    ECSensorEntityDescription(
        key="pop",
        name="Chance of precipitation",
        icon="mdi:weather-snowy-rainy",
        device_class=None,
        native_unit_of_measurement=PERCENTAGE,
        unit_convert=PERCENTAGE,
    ),
    ECSensorEntityDescription(
        key="precip_yesterday",
        name="Precipitation yesterday",
        icon="mdi:weather-snowy-rainy",
        device_class=None,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        unit_convert=LENGTH_INCHES,
    ),
    ECSensorEntityDescription(
        key="uv_index",
        name="UV Index",
        icon="mdi:weather-sunny-alert",
        device_class=None,
        native_unit_of_measurement=UV_INDEX,
        unit_convert=UV_INDEX,
    ),
    ECSensorEntityDescription(
        key="condition",
        name="Current Condition",
        icon="mdi:weather-partly-snowy-rainy",
        device_class=None,
        native_unit_of_measurement=None,
        unit_convert=None,
    ),
    ECSensorEntityDescription(
        key="icon_code",
        name="Icon Code",
        icon="mdi:weather-partly-snowy-rainy",
        device_class=None,
        native_unit_of_measurement=None,
        unit_convert=None,
    ),
    ECSensorEntityDescription(
        key="tendency",
        name="Tendency",
        icon="mdi:swap-vertical",
        device_class=None,
        native_unit_of_measurement=None,
        unit_convert=None,
    ),
    ECSensorEntityDescription(
        key="text_summary",
        name="Summary",
        icon="mdi:weather-partly-snowy-rainy",
        device_class=None,
        native_unit_of_measurement=None,
        unit_convert=None,
    ),
    ECSensorEntityDescription(
        key="wind_dir",
        name="Wind Direction",
        icon="mdi:sign-direction",
        device_class=None,
        native_unit_of_measurement=None,
        unit_convert=None,
    ),
    ECSensorEntityDescription(
        key="normal_low",
        name="Normal Low Temperature",
        icon="mdi:thermometer-chevron-down",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="normal_high",
        name="Normal High Temperature",
        icon="mdi:thermometer-chevron-up",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
)

AQHI_SENSOR = ECSensorEntityDescription(
    key="aqhi",
    name="AQHI",
    icon="mdi:lungs",
    device_class=None,
    native_unit_of_measurement=None,
    unit_convert=None,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the EC weather platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["weather_coordinator"]
    async_add_entities(
        ECSensor(
            coordinator, config_entry.data, description, hass.config.units.is_metric
        )
        for description in SENSOR_TYPES
    )
    async_add_entities(
        ECAlertSensor(coordinator, config_entry.data, alert) for alert in ALERTS
    )

    aqhi_coordinator = hass.data[DOMAIN][config_entry.entry_id]["aqhi_coordinator"]
    async_add_entities(
        [ECSensor(aqhi_coordinator, config_entry.data, AQHI_SENSOR, True)]
    )


class ECSensor(ECBaseEntity, SensorEntity):
    """An EC Sensor Entity."""

    def __init__(self, coordinator, config, description, is_metric):
        """Initialise the platform with a data instance."""
        super().__init__(coordinator, config, description.name)

        self._entity_description = description
        self._is_metric = is_metric
        if is_metric:
            self._attr_native_unit_of_measurement = (
                description.native_unit_of_measurement
            )
        else:
            self._attr_native_unit_of_measurement = description.unit_convert
        self._attr_device_class = description.device_class
        self._unique_id_tail = self._entity_description.key

    @property
    def native_value(self):
        """Return the state."""
        key = self._entity_description.key
        value = self._coordinator.data.current if key == "aqhi" else self.get_value(key)
        return convert(
            key,
            value,
            self._is_metric,
            self._entity_description.native_unit_of_measurement,
            self._entity_description.unit_convert,
        )

    @property
    def icon(self):
        """Return the icon."""
        return self._entity_description.icon


class ECAlertSensor(ECBaseEntity, SensorEntity):
    """An EC Sensor Entity for Alerts."""

    def __init__(self, coordinator, config, alert_name):
        """Initialise the platform with a data instance."""
        super().__init__(coordinator, config, f"{alert_name[1]} Alerts")

        self._alert_name = alert_name
        self._alert_attrs = None
        self._unique_id_tail = self._alert_name[0]

    @property
    def native_value(self):
        """Return the state."""
        value = self._coordinator.data.alerts.get(self._alert_name[0], {}).get("value")
        if value is None:
            return None

        self._alert_attrs = {}
        for index, alert in enumerate(value, start=1):
            self._alert_attrs[f"alert {index}"] = alert.get("title")
            self._alert_attrs[f"alert_time {index}"] = alert.get("date")

        return len(value)

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._alert_attrs

    @property
    def icon(self):
        """Return the icon."""
        return self._alert_name[2]
