"""Constants for Airly integration."""
from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)

from .model import AirlySensorEntityDescription

ATTR_API_ADVICE: Final = "ADVICE"
ATTR_API_CAQI: Final = "CAQI"
ATTR_API_CAQI_DESCRIPTION: Final = "DESCRIPTION"
ATTR_API_CAQI_LEVEL: Final = "LEVEL"
ATTR_API_HUMIDITY: Final = "HUMIDITY"
ATTR_API_PM10: Final = "PM10"
ATTR_API_PM1: Final = "PM1"
ATTR_API_PM25: Final = "PM25"
ATTR_API_PRESSURE: Final = "PRESSURE"
ATTR_API_TEMPERATURE: Final = "TEMPERATURE"

ATTR_ADVICE: Final = "advice"
ATTR_DESCRIPTION: Final = "description"
ATTR_LEVEL: Final = "level"
ATTR_LIMIT: Final = "limit"
ATTR_PERCENT: Final = "percent"

SUFFIX_PERCENT: Final = "PERCENT"
SUFFIX_LIMIT: Final = "LIMIT"

ATTRIBUTION: Final = "Data provided by Airly"
CONF_USE_NEAREST: Final = "use_nearest"
DEFAULT_NAME: Final = "Airly"
DOMAIN: Final = "airly"
LABEL_ADVICE: Final = "advice"
MANUFACTURER: Final = "Airly sp. z o.o."
MAX_UPDATE_INTERVAL: Final = 90
MIN_UPDATE_INTERVAL: Final = 5
NO_AIRLY_SENSORS: Final = "There are no Airly sensors in this area yet."

SENSOR_TYPES: tuple[AirlySensorEntityDescription, ...] = (
    AirlySensorEntityDescription(
        key=ATTR_API_CAQI,
        name=ATTR_API_CAQI,
        unit_of_measurement="CAQI",
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PM1,
        icon="mdi:blur",
        name=ATTR_API_PM1,
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PM25,
        icon="mdi:blur",
        name="PM2.5",
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PM10,
        icon="mdi:blur",
        name=ATTR_API_PM10,
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        name=ATTR_API_HUMIDITY.capitalize(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        value=lambda value: round(value, 1),
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PRESSURE,
        device_class=DEVICE_CLASS_PRESSURE,
        name=ATTR_API_PRESSURE.capitalize(),
        unit_of_measurement=PRESSURE_HPA,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        name=ATTR_API_TEMPERATURE.capitalize(),
        unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
        value=lambda value: round(value, 1),
    ),
)
