"""Imports for const.py."""

from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)

DOMAIN = "uhooair"
LOGGER = logging.getLogger(__package__)
APP_VERSION: int = 1

# Base component constants
NAME = "uHoo Integration"
MODEL = "uHoo Indoor Air Monitor"
MANUFACTURER = "uHoo, Inc."
VERSION = "1.0.0"
ISSUE_URL = "https://github.com/getuhoo/uhooair-homeassistant/issues"

UPDATE_INTERVAL = timedelta(seconds=300)

PLATFORMS = ["sensor"]

API_VIRUS = "virus_index"
API_MOLD = "mold_index"
API_TEMP = "temperature"
API_HUMIDITY = "humidity"
API_PM25 = "pm25"
API_TVOC = "tvoc"
API_CO2 = "co2"
API_CO = "co"
API_PRESSURE = "air_pressure"
API_OZONE = "ozone"
API_NO2 = "no2"
API_PM1 = "pm1"
API_PM4 = "pm4"
API_PM10 = "pm10"
API_CH2O = "ch2o"
API_LIGHT = "light"
API_SOUND = "sound"
API_H2S = "h2s"
API_NO = "no"
API_SO2 = "so2"
API_NH3 = "nh3"
API_OXYGEN = "oxygen"

ATTR_LABEL = "label"
ATTR_UNIQUE_ID = "unique_id"
SENSOR_TYPES = {
    API_CO: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.CO,
        ATTR_ICON: "mdi:molecule-co",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_MILLION,
        ATTR_LABEL: "Carbon monoxide",
        ATTR_UNIQUE_ID: API_CO,
    },
    API_CO2: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.CO2,
        ATTR_ICON: "mdi:molecule-co2",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_MILLION,
        ATTR_LABEL: "Carbon dioxide",
        ATTR_UNIQUE_ID: API_CO2,
    },
    API_PM25: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.PM25,  # DEVICE_CLASS_PM25 once supported
        ATTR_ICON: "mdi:blur",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_LABEL: "PM2.5",
        ATTR_UNIQUE_ID: API_PM25,
    },
    API_HUMIDITY: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
        ATTR_ICON: "mdi:water-percent",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_LABEL: "Humidity",
        ATTR_UNIQUE_ID: API_HUMIDITY,
    },
    API_TEMP: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        ATTR_LABEL: "Temperature",
        ATTR_UNIQUE_ID: API_TEMP,
    },
    API_PRESSURE: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
        ATTR_ICON: "mdi:gauge",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.HPA,
        ATTR_LABEL: "Air pressure",
        ATTR_UNIQUE_ID: API_PRESSURE,
    },
    API_TVOC: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,  # DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS once supported
        ATTR_ICON: "mdi:cloud",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_LABEL: "Total volatile organic compounds",
        ATTR_UNIQUE_ID: API_TVOC,
    },
    API_NO2: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.NITROGEN_DIOXIDE,  # DEVICE_CLASS_NITROGEN_DIOXIDE once supported
        ATTR_ICON: "mdi:cloud",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_LABEL: "Nitrogen dioxide",
        ATTR_UNIQUE_ID: API_NO2,
    },
    API_OZONE: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.OZONE,
        ATTR_ICON: "mdi:cloud",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_LABEL: "Ozone",
        ATTR_UNIQUE_ID: API_OZONE,
    },
    API_VIRUS: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.AQI,
        ATTR_ICON: "mdi:biohazard",
        ATTR_UNIT_OF_MEASUREMENT: "",
        ATTR_LABEL: "Virus index",
        ATTR_UNIQUE_ID: API_VIRUS,
    },
    API_MOLD: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.AQI,
        ATTR_ICON: "mdi:mushroom",
        ATTR_UNIT_OF_MEASUREMENT: "",
        ATTR_LABEL: "Mold index",
        ATTR_UNIQUE_ID: API_MOLD,
    },
}

AURA_SENSORS = {
    API_CH2O: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:chemical-weapon",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_LABEL: "Formaldehyde (CH2O)",
        ATTR_UNIQUE_ID: API_CH2O,
    },
    API_LIGHT: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:brightness-5",
        ATTR_UNIT_OF_MEASUREMENT: "lux",
        ATTR_LABEL: "Light intensity",
        ATTR_UNIQUE_ID: API_LIGHT,
    },
    API_SOUND: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:volume-high",
        ATTR_UNIT_OF_MEASUREMENT: "dB",
        ATTR_LABEL: "Sound level",
        ATTR_UNIQUE_ID: API_SOUND,
    },
    API_H2S: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:chemical-weapon",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_LABEL: "Hydrogen sulfide",
        ATTR_UNIQUE_ID: API_H2S,
    },
    API_NO: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:cloud",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_LABEL: "Nitric oxide",
        ATTR_UNIQUE_ID: API_NO,
    },
    API_SO2: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:cloud",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_LABEL: "Sulfur dioxide",
        ATTR_UNIQUE_ID: API_SO2,
    },
    API_NH3: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:cloud",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_LABEL: "Ammonia",
        ATTR_UNIQUE_ID: API_NH3,
    },
    API_OXYGEN: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:gas-cylinder",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_LABEL: "Oxygen",
        ATTR_UNIQUE_ID: API_OXYGEN,
    },
    API_PM1: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_LABEL: "PM1.0",
        ATTR_UNIQUE_ID: API_PM1,
    },
    API_PM4: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_LABEL: "PM4.0",
        ATTR_UNIQUE_ID: API_PM4,
    },
    API_PM10: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_LABEL: "PM10",
        ATTR_UNIQUE_ID: API_PM10,
    },
}

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a would be the official integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
