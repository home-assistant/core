"""Sensor data of the Renson ventilation unit."""
import logging

from renson_endura_delta.field_enum import (
    AIR_QUALITY_FIELD,
    BREEZE_LEVEL_FIELD,
    BREEZE_TEMPERATURE_FIELD,
    BYPASS_LEVEL_FIELD,
    BYPASS_TEMPERATURE_FIELD,
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
    HUMIDITY_FIELD,
    INDOOR_TEMP_FIELD,
    MANUAL_LEVEL_FIELD,
    NIGHT_POLLUTION_FIELD,
    NIGHTTIME_FIELD,
    OUTDOOR_TEMP_FIELD,
)
import renson_endura_delta.renson as renson
import voluptuous as vol

from homeassistant.components.renson.renson_descriptions import (
    RensonSensorEntityDescription,
)
from homeassistant.components.renson.renson_sensor import RensonSensor
from homeassistant.components.sensor import PLATFORM_SCHEMA, STATE_CLASS_MEASUREMENT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, DEVICE_CLASS_HUMIDITY, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONCENTRATION_PARTS_PER_CUBIC_METER, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST, default=[]): cv.string}
)

sensor_descriptions = [
    RensonSensorEntityDescription(
        key="CO2_QUALITY_FIELD",
        name="CO2 quality",
        field=CO2_QUALITY_FIELD,
        raw_format=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    RensonSensorEntityDescription(
        key="AIR_QUALITY_FIELD",
        name="Air quality",
        field=AIR_QUALITY_FIELD,
        raw_format=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    RensonSensorEntityDescription(
        key="CO2_FIELD",
        name="CO2 quality value",
        field=CO2_FIELD,
        raw_format=True,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class="carbon_dioxide",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
    ),
    RensonSensorEntityDescription(
        key="AIR_FIELD",
        name="Air quality value",
        field=AIR_QUALITY_FIELD,
        state_class=STATE_CLASS_MEASUREMENT,
        raw_format=True,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
    ),
    RensonSensorEntityDescription(
        key="CURRENT_LEVEL_FIELD_RAW",
        name="Ventilation level raw",
        field=CURRENT_LEVEL_FIELD,
        state_class=STATE_CLASS_MEASUREMENT,
        raw_format=True,
    ),
    RensonSensorEntityDescription(
        key="CURRENT_LEVEL_FIELD",
        name="Ventilation level",
        state_class=STATE_CLASS_MEASUREMENT,
        field=CURRENT_LEVEL_FIELD,
        raw_format=False,
    ),
    RensonSensorEntityDescription(
        key="CURRENT_AIRFLOW_EXTRACT_FIELD",
        name="Total airflow out",
        field=CURRENT_AIRFLOW_EXTRACT_FIELD,
        raw_format=False,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement="m³/h",
    ),
    RensonSensorEntityDescription(
        key="CURRENT_AIRFLOW_INGOING_FIELD",
        name="Total airflow in",
        field=CURRENT_AIRFLOW_INGOING_FIELD,
        raw_format=False,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement="m³/h",
    ),
    RensonSensorEntityDescription(
        key="OUTDOOR_TEMP_FIELD",
        name="Outdoor air temperature",
        field=OUTDOOR_TEMP_FIELD,
        raw_format=False,
        device_class="temperature",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RensonSensorEntityDescription(
        key="INDOOR_TEMP_FIELD",
        name="Extract air temperature",
        field=INDOOR_TEMP_FIELD,
        raw_format=False,
        device_class="temperature",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RensonSensorEntityDescription(
        key="FILTER_REMAIN_FIELD",
        name="Filter change",
        field=FILTER_REMAIN_FIELD,
        raw_format=False,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement="days",
    ),
    RensonSensorEntityDescription(
        key="HUMIDITY_FIELD",
        name="Relative humidity",
        field=HUMIDITY_FIELD,
        raw_format=False,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    RensonSensorEntityDescription(
        key="MANUAL_LEVEL_FIELD",
        name="Manual level",
        field=MANUAL_LEVEL_FIELD,
        raw_format=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    RensonSensorEntityDescription(
        key="BREEZE_TEMPERATURE_FIELD",
        name="Breeze temperature",
        field=BREEZE_TEMPERATURE_FIELD,
        raw_format=False,
        device_class=TEMP_CELSIUS,
        native_unit_of_measurement=TEMP_CELSIUS,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="BREEZE_LEVEL_FIELD",
        name="Breeze level",
        field=BREEZE_LEVEL_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="DAYTIME_FIELD",
        name="Start day time",
        field=DAYTIME_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="NIGHTTIME_FIELD",
        name="Start night time",
        field=NIGHTTIME_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="DAY_POLLUTION_FIELD",
        name="Day pollution level",
        field=DAY_POLLUTION_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="NIGHT_POLLUTION_FIELD",
        name="Night pollution level",
        field=NIGHT_POLLUTION_FIELD,
        raw_format=False,
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="CO2_THRESHOLD_FIELD",
        name="CO2 threshold",
        field=CO2_THRESHOLD_FIELD,
        raw_format=False,
        native_unit_of_measurement="ppm",
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="CO2_HYSTERESIS_FIELD",
        name="CO2 hysteresis",
        field=CO2_HYSTERESIS_FIELD,
        raw_format=False,
        native_unit_of_measurement="ppm",
        entity_registry_enabled_default=False,
    ),
    RensonSensorEntityDescription(
        key="BYPASS_TEMPERATURE_FIELD",
        name="Bypass activation temperature",
        field=BYPASS_TEMPERATURE_FIELD,
        raw_format=False,
        device_class="temperature",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    RensonSensorEntityDescription(
        key="BYPASS_LEVEL_FIELD",
        name="Bypass level",
        field=BYPASS_LEVEL_FIELD,
        raw_format=False,
        device_class="power_factor",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    RensonSensorEntityDescription(
        key="FILTER_PRESET_FIELD",
        name="Filter preset time",
        field=FILTER_PRESET_FIELD,
        raw_format=False,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement="days",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities, discovery_info=None
):
    """Call the Renson integration to setup."""

    renson_api: renson.RensonVentilation = hass.data[DOMAIN][config.entry_id]

    entities: list = []
    for description in sensor_descriptions:
        entities.append(RensonSensor(description, renson_api))
    async_add_entities(entities)
