"""Sensor data of the Renson ventilation unit."""
import logging

from rensonVentilationLib.fieldEnum import (
    AIR_QUALITY_CONTROL_FIELD,
    AIR_QUALITY_FIELD,
    BREEZE_ENABLE_FIELD,
    BREEZE_LEVEL_FIELD,
    BREEZE_MET_FIELD,
    BREEZE_TEMPERATURE_FIELD,
    BYPASS_LEVEL_FIELD,
    BYPASS_TEMPERATURE_FIELD,
    CO2_CONTROL_FIELD,
    CO2_FIELD,
    CO2_HYSTERESIS_FIELD,
    CO2_QUALITY_FIELD,
    CO2_THRESHOLD_FIELD,
    CURRENT_AIRFLOW_EXTRACT_FIELD,
    CURRENT_AIRFLOW_INGOING_FIELD,
    CURRENT_LEVEL_FIELD,
    DAY_POLLUTION_FIELD,
    DAYTIME_FIELD,
    FILTER_PRESET_FIELD,
    FILTER_REMAIN_FIELD,
    FROST_PROTECTION_FIELD,
    HUMIDITY_CONTROL_FIELD,
    HUMIDITY_FIELD,
    INDOOR_TEMP_FIELD,
    MANUAL_LEVEL_FIELD,
    NIGHT_POLLUTION_FIELD,
    NIGHTTIME_FIELD,
    OUTDOOR_TEMP_FIELD,
    PREHEATER_FIELD,
    TIME_AND_DATE_FIELD,
)
import rensonVentilationLib.renson as renson
import voluptuous as vol

from homeassistant.components.renson.firmwaresensor import FirmwareSensor
from homeassistant.components.renson.rensonBinarySensor import RensonBinarySensor
from homeassistant.components.renson.sensorvalue import SensorValue
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import (
    AIR_DESC,
    AIR_QUALITY_CONTROL_DESC,
    AIR_QUALITY_DESC,
    BREEZE_ENABLE_DESC,
    BREEZE_LEVEL_DESC,
    BREEZE_MET_DESC,
    BREEZE_TEMPERATURE_DESC,
    BYPASS_LEVEL_DESC,
    BYPASS_TEMPERATURE_DESC,
    CO2_CONTROL_DESC,
    CO2_DESC,
    CO2_HYSTERESIS_DESC,
    CO2_QUALITY_DESC,
    CO2_THRESHOLD_DESC,
    CURRENT_AIRFLOW_EXTRACT_DESC,
    CURRENT_AIRFLOW_INGOING_DESC,
    CURRENT_LEVEL_DESC,
    CURRENT_LEVEL_RAW_DESC,
    DAY_POLLUTION_DESC,
    DAYTIME_DESC,
    DOMAIN,
    FILTER_PRESET_DESC,
    FILTER_REMAIN_DESC,
    FROST_PROTECTION_DESC,
    HUMIDITY_CONTROL_DESC,
    HUMIDITY_DESC,
    INDOOR_TEMP_DESC,
    MANUAL_LEVEL_DESC,
    NIGHT_POLLUTION_DESC,
    NIGHTTIME_DESC,
    OUTDOOR_TEMP_DESC,
    PREHEATER_DESC,
    TIME_AND_DATE_DESC,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST, default=[]): cv.string}
)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities, discovery_info=None
):
    """Call the Renson integration to setup."""

    rensonApi: renson.RensonVentilation = hass.data[DOMAIN][config.entry_id]

    async_add_entities(
        [
            SensorValue(CO2_QUALITY_DESC, CO2_QUALITY_FIELD, rensonApi, False),
            SensorValue(AIR_QUALITY_DESC, AIR_QUALITY_FIELD, rensonApi, False),
            SensorValue(CO2_DESC, CO2_FIELD, rensonApi, False),
            SensorValue(
                AIR_DESC,
                AIR_QUALITY_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                CURRENT_LEVEL_RAW_DESC,
                CURRENT_LEVEL_FIELD,
                rensonApi,
                True,
            ),
            SensorValue(CURRENT_LEVEL_DESC, CURRENT_LEVEL_FIELD, rensonApi, False),
            SensorValue(
                CURRENT_AIRFLOW_EXTRACT_DESC,
                CURRENT_AIRFLOW_EXTRACT_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                CURRENT_AIRFLOW_INGOING_DESC,
                CURRENT_AIRFLOW_INGOING_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                OUTDOOR_TEMP_DESC,
                OUTDOOR_TEMP_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                INDOOR_TEMP_DESC,
                INDOOR_TEMP_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                FILTER_REMAIN_DESC,
                FILTER_REMAIN_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                HUMIDITY_DESC,
                HUMIDITY_FIELD,
                rensonApi,
                False,
            ),
            RensonBinarySensor(
                FROST_PROTECTION_DESC,
                FROST_PROTECTION_FIELD,
                rensonApi,
            ),
            SensorValue(
                MANUAL_LEVEL_DESC,
                MANUAL_LEVEL_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                TIME_AND_DATE_DESC,
                TIME_AND_DATE_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                BREEZE_TEMPERATURE_DESC,
                BREEZE_TEMPERATURE_FIELD,
                rensonApi,
                False,
            ),
            RensonBinarySensor(
                BREEZE_ENABLE_DESC,
                BREEZE_ENABLE_FIELD,
                rensonApi,
            ),
            SensorValue(
                BREEZE_LEVEL_DESC,
                BREEZE_LEVEL_FIELD,
                rensonApi,
                False,
            ),
            RensonBinarySensor(
                BREEZE_MET_DESC,
                BREEZE_MET_FIELD,
                rensonApi,
            ),
            SensorValue(
                DAYTIME_DESC,
                DAYTIME_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                NIGHTTIME_DESC,
                NIGHTTIME_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                DAY_POLLUTION_DESC,
                DAY_POLLUTION_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                NIGHT_POLLUTION_DESC,
                NIGHT_POLLUTION_FIELD,
                rensonApi,
                False,
            ),
            RensonBinarySensor(
                HUMIDITY_CONTROL_DESC,
                HUMIDITY_CONTROL_FIELD,
                rensonApi,
            ),
            RensonBinarySensor(
                AIR_QUALITY_CONTROL_DESC,
                AIR_QUALITY_CONTROL_FIELD,
                rensonApi,
            ),
            RensonBinarySensor(
                CO2_CONTROL_DESC,
                CO2_CONTROL_FIELD,
                rensonApi,
            ),
            SensorValue(
                CO2_THRESHOLD_DESC,
                CO2_THRESHOLD_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                CO2_HYSTERESIS_DESC,
                CO2_HYSTERESIS_FIELD,
                rensonApi,
                False,
            ),
            RensonBinarySensor(
                PREHEATER_DESC,
                PREHEATER_FIELD,
                rensonApi,
            ),
            SensorValue(
                BYPASS_TEMPERATURE_DESC,
                BYPASS_TEMPERATURE_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                BYPASS_LEVEL_DESC,
                BYPASS_LEVEL_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                FILTER_PRESET_DESC,
                FILTER_PRESET_FIELD,
                rensonApi,
                False,
            ),
            FirmwareSensor(rensonApi, hass),
        ]
    )
