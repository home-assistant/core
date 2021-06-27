"""Constants for Airly integration."""
from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)

from .model import SensorDescription

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
ATTR_LABEL: Final = "label"
ATTR_LEVEL: Final = "level"
ATTR_LIMIT: Final = "limit"
ATTR_PERCENT: Final = "percent"
ATTR_UNIT: Final = "unit"
ATTR_VALUE: Final = "value"

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

SENSOR_TYPES: dict[str, SensorDescription] = {
    ATTR_API_CAQI: {
        ATTR_LABEL: ATTR_API_CAQI,
        ATTR_UNIT: "CAQI",
        ATTR_VALUE: round,
    },
    ATTR_API_PM1: {
        ATTR_ICON: "mdi:blur",
        ATTR_LABEL: ATTR_API_PM1,
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: round,
    },
    ATTR_API_PM25: {
        ATTR_ICON: "mdi:blur",
        ATTR_LABEL: "PM2.5",
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: round,
    },
    ATTR_API_PM10: {
        ATTR_ICON: "mdi:blur",
        ATTR_LABEL: ATTR_API_PM10,
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: round,
    },
    ATTR_API_HUMIDITY: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_LABEL: ATTR_API_HUMIDITY.capitalize(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: lambda value: round(value, 1),
    },
    ATTR_API_PRESSURE: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        ATTR_LABEL: ATTR_API_PRESSURE.capitalize(),
        ATTR_UNIT: PRESSURE_HPA,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: round,
    },
    ATTR_API_TEMPERATURE: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_LABEL: ATTR_API_TEMPERATURE.capitalize(),
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: lambda value: round(value, 1),
    },
}
