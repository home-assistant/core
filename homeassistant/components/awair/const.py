"""Constants for the Awair component."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from python_awair.devices import AwairDevice

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    LIGHT_LUX,
    PERCENTAGE,
    TEMP_CELSIUS,
)

API_CO2 = "carbon_dioxide"
API_DUST = "dust"
API_HUMID = "humidity"
API_LUX = "illuminance"
API_PM10 = "particulate_matter_10"
API_PM25 = "particulate_matter_2_5"
API_SCORE = "score"
API_SPL_A = "sound_pressure_level"
API_TEMP = "temperature"
API_TIMEOUT = 20
API_VOC = "volatile_organic_compounds"

ATTRIBUTION = "Awair air quality sensor"

ATTR_ICON = "icon"
ATTR_LABEL = "label"
ATTR_UNIT = "unit"
ATTR_UNIQUE_ID = "unique_id"

DOMAIN = "awair"

DUST_ALIASES = [API_PM25, API_PM10]

LOGGER = logging.getLogger(__package__)

UPDATE_INTERVAL = timedelta(minutes=5)

SENSOR_TYPES = {
    API_SCORE: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_UNIT: PERCENTAGE,
        ATTR_LABEL: "Awair score",
        ATTR_UNIQUE_ID: "score",  # matches legacy format
    },
    API_HUMID: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_ICON: None,
        ATTR_UNIT: PERCENTAGE,
        ATTR_LABEL: "Humidity",
        ATTR_UNIQUE_ID: "HUMID",  # matches legacy format
    },
    API_LUX: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE,
        ATTR_ICON: None,
        ATTR_UNIT: LIGHT_LUX,
        ATTR_LABEL: "Illuminance",
        ATTR_UNIQUE_ID: "illuminance",
    },
    API_SPL_A: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:ear-hearing",
        ATTR_UNIT: "dBa",
        ATTR_LABEL: "Sound level",
        ATTR_UNIQUE_ID: "sound_level",
    },
    API_VOC: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:cloud",
        ATTR_UNIT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_LABEL: "Volatile organic compounds",
        ATTR_UNIQUE_ID: "VOC",  # matches legacy format
    },
    API_TEMP: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_LABEL: "Temperature",
        ATTR_UNIQUE_ID: "TEMP",  # matches legacy format
    },
    API_PM25: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_LABEL: "PM2.5",
        ATTR_UNIQUE_ID: "PM25",  # matches legacy format
    },
    API_PM10: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_LABEL: "PM10",
        ATTR_UNIQUE_ID: "PM10",  # matches legacy format
    },
    API_CO2: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:cloud",
        ATTR_UNIT: CONCENTRATION_PARTS_PER_MILLION,
        ATTR_LABEL: "Carbon dioxide",
        ATTR_UNIQUE_ID: "CO2",  # matches legacy format
    },
}


@dataclass
class AwairResult:
    """Wrapper class to hold an awair device and set of air data."""

    device: AwairDevice
    air_data: dict
