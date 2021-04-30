"""Constants for Airly integration."""
from __future__ import annotations

from typing import Final

from homeassistant.const import (
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
ATTR_API_PM1: Final = "PM1"
ATTR_API_PM10: Final = "PM10"
ATTR_API_PM10_LIMIT: Final = "PM10_LIMIT"
ATTR_API_PM10_PERCENT: Final = "PM10_PERCENT"
ATTR_API_PM25: Final = "PM25"
ATTR_API_PM25_LIMIT: Final = "PM25_LIMIT"
ATTR_API_PM25_PERCENT: Final = "PM25_PERCENT"
ATTR_API_PRESSURE: Final = "PRESSURE"
ATTR_API_TEMPERATURE: Final = "TEMPERATURE"

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
    ATTR_API_PM1: {
        "device_class": None,
        "icon": "mdi:blur",
        "label": ATTR_API_PM1,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    ATTR_API_HUMIDITY: {
        "device_class": DEVICE_CLASS_HUMIDITY,
        "icon": None,
        "label": ATTR_API_HUMIDITY.capitalize(),
        "unit": PERCENTAGE,
    },
    ATTR_API_PRESSURE: {
        "device_class": DEVICE_CLASS_PRESSURE,
        "icon": None,
        "label": ATTR_API_PRESSURE.capitalize(),
        "unit": PRESSURE_HPA,
    },
    ATTR_API_TEMPERATURE: {
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "icon": None,
        "label": ATTR_API_TEMPERATURE.capitalize(),
        "unit": TEMP_CELSIUS,
    },
}
