"""Constants for the Awair component."""

from collections import namedtuple
from datetime import timedelta
import logging

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)

AwairResult = namedtuple("AwairResult", ["device", "air_data"])

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

# Some of these names are historical, because this integration
# created sensors with names that matched the API somewhat
# directly. If air quality device classes are standardized
# across home assistant, then we should adjust these as well.
# For example:
# score -> air_quality_index
# CO2   -> carbon_dioxide
# PM10  -> particulate_matter_10
# PM2.5 -> particulate_matter_2_5
# VOC   -> volatile_organic_compounds

DEVICE_CLASS_AIR_QUALITY_INDEX = "score"
DEVICE_CLASS_CO2 = "CO2"
DEVICE_CLASS_PM_10 = "PM10"
DEVICE_CLASS_PM_2_5 = "PM2.5"
DEVICE_CLASS_SOUND_LEVEL = "sound_level"
DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS = "VOC"

DOMAIN = "awair"

DUST_ALIASES = [API_PM25, API_PM10]

LOGGER = logging.getLogger(__package__)

UPDATE_INTERVAL = timedelta(minutes=5)

SENSOR_TYPES = {
    API_SCORE: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_AIR_QUALITY_INDEX,
        ATTR_ICON: "mdi:blur",
        ATTR_UNIT: UNIT_PERCENTAGE,
        ATTR_LABEL: "Awair Score",
    },
    API_HUMID: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_ICON: "mdi:water-percent",
        ATTR_UNIT: UNIT_PERCENTAGE,
        ATTR_LABEL: "Humidity",
    },
    API_LUX: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_ILLUMINANCE,
        ATTR_ICON: "mdi:lightbulb",
        ATTR_UNIT: "lux",
        ATTR_LABEL: "Illuminance",
    },
    API_SPL_A: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_SOUND_LEVEL,
        ATTR_ICON: "mdi:ear-hearing",
        ATTR_UNIT: "dBa",
        ATTR_LABEL: "Sound level",
    },
    API_VOC: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
        ATTR_ICON: "mdi:cloud",
        ATTR_UNIT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_LABEL: "Volatile organic compounds",
    },
    API_TEMP: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_LABEL: "Temperature",
    },
    API_PM25: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PM_2_5,
        ATTR_ICON: "mdi:blur",
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_LABEL: "PM2.5",
    },
    API_PM10: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PM_10,
        ATTR_ICON: "mdi:blur",
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_LABEL: "PM10",
    },
    API_CO2: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_CO2,
        ATTR_ICON: "mdi:cloud",
        ATTR_UNIT: CONCENTRATION_PARTS_PER_MILLION,
        ATTR_LABEL: "Carbon dioxide",
    },
}
