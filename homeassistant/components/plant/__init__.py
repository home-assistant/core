"""Support for monitoring plants.

DEVELOPMENT OF THE PLANT INTEGRATION IS FROZEN
PENDING A DESIGN EVALUATION.
"""

import logging

import probatio

from homeassistant.const import CONF_SENSORS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CHECK_DAYS,
    CONF_MAX_BRIGHTNESS,
    CONF_MAX_CONDUCTIVITY,
    CONF_MAX_MOISTURE,
    CONF_MAX_TEMPERATURE,
    CONF_MIN_BATTERY_LEVEL,
    CONF_MIN_BRIGHTNESS,
    CONF_MIN_CONDUCTIVITY,
    CONF_MIN_MOISTURE,
    CONF_MIN_TEMPERATURE,
    DEFAULT_CHECK_DAYS,
    DEFAULT_MAX_CONDUCTIVITY,
    DEFAULT_MAX_MOISTURE,
    DEFAULT_MIN_BATTERY_LEVEL,
    DEFAULT_MIN_CONDUCTIVITY,
    DEFAULT_MIN_MOISTURE,
    DOMAIN,
    READING_BATTERY,
    READING_BRIGHTNESS,
    READING_CONDUCTIVITY,
    READING_MOISTURE,
    READING_TEMPERATURE,
)
from .entity import Plant

_LOGGER = logging.getLogger(__name__)

CONF_SENSOR_BATTERY_LEVEL = READING_BATTERY
CONF_SENSOR_MOISTURE = READING_MOISTURE
CONF_SENSOR_CONDUCTIVITY = READING_CONDUCTIVITY
CONF_SENSOR_TEMPERATURE = READING_TEMPERATURE
CONF_SENSOR_BRIGHTNESS = READING_BRIGHTNESS


SCHEMA_SENSORS = probatio.Schema(
    {
        probatio.Optional(CONF_SENSOR_BATTERY_LEVEL): cv.entity_id,
        probatio.Optional(CONF_SENSOR_MOISTURE): cv.entity_id,
        probatio.Optional(CONF_SENSOR_CONDUCTIVITY): cv.entity_id,
        probatio.Optional(CONF_SENSOR_TEMPERATURE): cv.entity_id,
        probatio.Optional(CONF_SENSOR_BRIGHTNESS): cv.entity_id,
    }
)

PLANT_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_SENSORS): probatio.Schema(SCHEMA_SENSORS),
        probatio.Optional(
            CONF_MIN_BATTERY_LEVEL, default=DEFAULT_MIN_BATTERY_LEVEL
        ): cv.positive_int,
        probatio.Optional(CONF_MIN_TEMPERATURE): probatio.Coerce(float),
        probatio.Optional(CONF_MAX_TEMPERATURE): probatio.Coerce(float),
        probatio.Optional(
            CONF_MIN_MOISTURE, default=DEFAULT_MIN_MOISTURE
        ): cv.positive_int,
        probatio.Optional(
            CONF_MAX_MOISTURE, default=DEFAULT_MAX_MOISTURE
        ): cv.positive_int,
        probatio.Optional(
            CONF_MIN_CONDUCTIVITY, default=DEFAULT_MIN_CONDUCTIVITY
        ): cv.positive_int,
        probatio.Optional(
            CONF_MAX_CONDUCTIVITY, default=DEFAULT_MAX_CONDUCTIVITY
        ): cv.positive_int,
        probatio.Optional(CONF_MIN_BRIGHTNESS): cv.positive_int,
        probatio.Optional(CONF_MAX_BRIGHTNESS): cv.positive_int,
        probatio.Optional(CONF_CHECK_DAYS, default=DEFAULT_CHECK_DAYS): cv.positive_int,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: {cv.string: PLANT_SCHEMA}}, extra=probatio.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Plant component."""
    component = EntityComponent[Plant](_LOGGER, DOMAIN, hass)

    entities = []
    for plant_name, plant_config in config[DOMAIN].items():
        _LOGGER.info("Added plant %s", plant_name)
        entity = Plant(plant_name, plant_config)
        entities.append(entity)

    await component.async_add_entities(entities)
    return True
