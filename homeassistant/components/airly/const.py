"""Constants for Airly integration."""
from __future__ import annotations

from typing import TypedDict

from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)

ATTR_API_ADVICE = "ADVICE"
ATTR_API_CAQI = "CAQI"
ATTR_API_CAQI_DESCRIPTION = "DESCRIPTION"
ATTR_API_CAQI_LEVEL = "LEVEL"
ATTR_API_HUMIDITY = "HUMIDITY"
ATTR_API_PM1 = "PM1"
ATTR_API_PM10 = "PM10"
ATTR_API_PM10_LIMIT = "PM10_LIMIT"
ATTR_API_PM10_PERCENT = "PM10_PERCENT"
ATTR_API_PM25 = "PM25"
ATTR_API_PM25_LIMIT = "PM25_LIMIT"
ATTR_API_PM25_PERCENT = "PM25_PERCENT"
ATTR_API_PRESSURE = "PRESSURE"
ATTR_API_TEMPERATURE = "TEMPERATURE"

ATTRIBUTION = "Data provided by Airly"
CONF_USE_NEAREST = "use_nearest"
DEFAULT_NAME = "Airly"
DOMAIN = "airly"
LABEL_ADVICE = "advice"
MANUFACTURER = "Airly sp. z o.o."
MAX_UPDATE_INTERVAL = 90
MIN_UPDATE_INTERVAL = 5
NO_AIRLY_SENSORS = "There are no Airly sensors in this area yet."

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


class SensorDescription(TypedDict):
    """Sensor description class."""

    device_class: str | None
    icon: str | None
    label: str
    unit: str
