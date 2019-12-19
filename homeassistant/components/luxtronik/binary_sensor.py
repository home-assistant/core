"""
Support for monitoring the state of a Luxtronik heatpump.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/luxtronik/
"""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorDevice
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_ICON, CONF_ID, CONF_SENSORS
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify

from . import DATA_LUXTRONIK, ENTITY_ID_FORMAT
from .const import (
    CONF_CALCULATIONS,
    CONF_GROUP,
    CONF_INVERT_STATE,
    CONF_PARAMETERS,
    CONF_VISIBILITIES,
)

ICON_ON = "mdi:check-circle-outline"
ICON_OFF = "mdi:circle-outline"

_LOGGER = logging.getLogger(__name__)

DEFAULT_DEVICE_CLASS = "binary_sensor"

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
                    vol.Optional(CONF_INVERT_STATE, default=False): cv.boolean,
                }
            ],
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Luxtronik binary sensor."""
    luxtronik = hass.data.get(DATA_LUXTRONIK)
    if not luxtronik:
        return False

    sensors = config.get(CONF_SENSORS)

    entities = []
    for sensor_cfg in sensors:
        sensor = luxtronik.get_sensor(sensor_cfg[CONF_GROUP], sensor_cfg[CONF_ID])
        if sensor:
            entities.append(LuxtronikBinarySensor(luxtronik, sensor, sensor_cfg))
        else:
            _LOGGER.warning(
                "Invalid Luxtronik ID %s in group %s",
                sensor_cfg[CONF_ID],
                sensor_cfg[CONF_GROUP],
            )

    add_entities(entities, True)


class LuxtronikBinarySensor(BinarySensorDevice):
    """Representation of a Luxtronik binary sensor."""

    def __init__(self, luxtronik, sensor, sensor_cfg):
        """Initialize a new Luxtronik binary sensor."""
        self._luxtronik = luxtronik
        self._sensor = sensor
        self._name = sensor_cfg[CONF_FRIENDLY_NAME]
        self._icon = sensor_cfg[CONF_ICON]
        self._invert = sensor_cfg[CONF_INVERT_STATE]

    @property
    def entity_id(self):
        """Return the entity_id of the sensor."""
        if not self._name:
            return ENTITY_ID_FORMAT.format(slugify(self._sensor.name))
        return ENTITY_ID_FORMAT.format(slugify(self._name))

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._icon:
            return self._icon
        if not self.is_on:
            return ICON_OFF
        return ICON_ON

    @property
    def name(self):
        """Return the name of the sensor."""
        if not self._name:
            return self._sensor.name
        return self._name

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        if self._invert:
            return not self._sensor.value
        return self._sensor.value

    @property
    def device_class(self):
        """Return the dvice class."""
        return DEFAULT_DEVICE_CLASS

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        self._luxtronik.update()
