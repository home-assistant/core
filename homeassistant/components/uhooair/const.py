"""Imports for const.py."""

from datetime import timedelta
import logging

from uhooapi import Client
import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_API_KEY,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
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


# Define sensor types using EntityDescription
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=API_CO,
        translation_key=API_CO,  # This will create "carbon_monoxide" in translations
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=API_CO2,
        translation_key=API_CO2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=API_PM25,
        translation_key=API_PM25,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=API_HUMIDITY,
        translation_key=API_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=API_TEMP,
        translation_key=API_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # Base unit
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=API_PRESSURE,
        translation_key=API_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=API_TVOC,
        translation_key=API_TVOC,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=API_NO2,
        translation_key=API_NO2,
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=API_OZONE,
        translation_key=API_OZONE,
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=API_VIRUS,
        translation_key=API_VIRUS,
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement="",  # Unitless
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=API_MOLD,
        translation_key=API_MOLD,
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement="",  # Unitless
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)

type UhooConfigEntry = ConfigEntry[Client]
