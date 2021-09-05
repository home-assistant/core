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

from homeassistant.components.renson_endura_delta.firmwaresensor import FirmwareSensor
from homeassistant.components.renson_endura_delta.sensorvalue import SensorValue
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

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
            SensorValue("CO2", "", "", CO2_FIELD, rensonApi, False),
            SensorValue("Air quality", "", "", AIR_QUALITY_FIELD, rensonApi, False),
            SensorValue(
                "CO2 value", "carbon_dioxide", "ppm", CO2_FIELD, rensonApi, False
            ),
            SensorValue(
                "Air quality value",
                "",
                "ppm",
                AIR_QUALITY_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Ventilation level raw",
                "",
                "",
                CURRENT_LEVEL_FIELD,
                rensonApi,
                True,
            ),
            SensorValue(
                "Ventilation level", "", "", CURRENT_LEVEL_FIELD, rensonApi, False
            ),
            SensorValue(
                "Total airflow out",
                "",
                "m³/h",
                CURRENT_AIRFLOW_EXTRACT_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Total airflow in",
                "",
                "m³/h",
                CURRENT_AIRFLOW_INGOING_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Outdoor air temperature",
                "temperature",
                TEMP_CELSIUS,
                OUTDOOR_TEMP_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Extract air temperature",
                "temperature",
                TEMP_CELSIUS,
                INDOOR_TEMP_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Filter change",
                "",
                "days",
                FILTER_REMAIN_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Relative humidity",
                "humidity",
                "%",
                HUMIDITY_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Frost protection active",
                "",
                "",
                FROST_PROTECTION_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Manual level",
                "",
                "",
                MANUAL_LEVEL_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "System time",
                "timestamp",
                "",
                TIME_AND_DATE_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Breeze temperature",
                "temperature",
                TEMP_CELSIUS,
                BREEZE_TEMPERATURE_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Breeze enabled",
                "",
                "",
                BREEZE_ENABLE_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Breeze level",
                "",
                "",
                BREEZE_LEVEL_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Breeze conditions met",
                "",
                "",
                BREEZE_MET_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Start day time",
                "",
                "",
                DAYTIME_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Start night time",
                "",
                "",
                NIGHTTIME_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Day pollution level",
                "",
                "",
                DAY_POLLUTION_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Night pollution level",
                "",
                "",
                NIGHT_POLLUTION_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Humidity control enabled",
                "",
                "",
                HUMIDITY_CONTROL_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Air quality control enabled",
                "",
                "",
                AIR_QUALITY_CONTROL_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "CO2 control enabled",
                "",
                "",
                CO2_CONTROL_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "CO2 threshold",
                "",
                "ppm",
                CO2_THRESHOLD_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "CO2 hysteresis",
                "",
                "ppm",
                CO2_HYSTERESIS_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Preheater enabled",
                "",
                "",
                PREHEATER_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Bypass activation temperature",
                "temperature",
                TEMP_CELSIUS,
                BYPASS_TEMPERATURE_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Bypass level",
                "power_factor",
                "%",
                BYPASS_LEVEL_FIELD,
                rensonApi,
                False,
            ),
            SensorValue(
                "Filter preset time",
                "",
                "days",
                FILTER_PRESET_FIELD,
                rensonApi,
                False,
            ),
            FirmwareSensor(rensonApi, hass),
        ]
    )
