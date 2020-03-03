"""Support for Luxtronik heatpump sensors."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_ICON, CONF_ID, CONF_SENSORS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from . import DOMAIN, ENTITY_ID_FORMAT
from .const import (
    CONF_CALCULATIONS,
    CONF_GROUP,
    CONF_PARAMETERS,
    CONF_VISIBILITIES,
    DEVICE_CLASSES,
    ICONS,
    UNITS,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_DEVICE_CLASS = "sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_GROUP): vol.All(
                        cv.string,
                        vol.Any(CONF_PARAMETERS, CONF_CALCULATIONS, CONF_VISIBILITIES),
                    ),
                    vol.Required(CONF_ID): cv.string,
                    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
                    vol.Optional(CONF_ICON): cv.string,
                }
            ],
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Luxtronik sensor."""
    luxtronik = hass.data.get(DOMAIN)
    if not luxtronik:
        return False

    sensors = config.get(CONF_SENSORS)

    entities = []
    for sensor_cfg in sensors:
        sensor = luxtronik.get_sensor(sensor_cfg[CONF_GROUP], sensor_cfg[CONF_ID])
        if sensor:
            entities.append(LuxtronikSensor(luxtronik, sensor, sensor_cfg))
        else:
            _LOGGER.warning(
                "Invalid Luxtronik ID %s in group %s",
                sensor_cfg[CONF_ID],
                sensor_cfg[CONF_GROUP],
            )

    add_entities(entities, True)


class LuxtronikSensor(Entity):
    """Representation of a Luxtronik sensor."""

    def __init__(self, luxtronik, sensor, sensor_cfg):
        """Initialize a new Luxtronik sensor."""
        self._luxtronik = luxtronik
        self._sensor = sensor
        self._name = sensor_cfg[CONF_FRIENDLY_NAME]
        self._icon = sensor_cfg[CONF_ICON]

    @property
    def entity_id(self):
        """Return the entity_id of the sensor."""
        if not self._name:
            return ENTITY_ID_FORMAT.format(slugify(self._sensor.name))
        return ENTITY_ID_FORMAT.format(slugify(self._name))

    @property
    def name(self):
        """Return the name of the sensor."""
        if not self._name:
            return self._sensor.name
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if not self._icon:
            return ICONS.get(self._sensor.measurement_type)
        return self._icon

    @property
    def state(self):
        """Return the sensor state."""
        return self._sensor.value

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEVICE_CLASSES.get(self._sensor.measurement_type, DEFAULT_DEVICE_CLASS)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return UNITS.get(self._sensor.measurement_type)

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        self._luxtronik.update()
