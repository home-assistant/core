"""
Support for monitoring the state of a Luxtronik heatpump.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.luxtronik/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_ICON
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from . import (
    CONF_SENSORS,
    CONF_ID,
    CONF_GROUP,
    CONF_PARAMETERS,
    CONF_CALCULATIONS,
    CONF_VISIBILITIES,
    DATA_LUXTRONIK,
    ENTITY_ID_FORMAT,
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
                    vol.Optional(CONF_FRIENDLY_NAME, default=""): cv.string,
                    vol.Optional(CONF_ICON, default=""): cv.string,
                }
            ],
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Luxtronik sensor."""
    luxtronik = hass.data.get(DATA_LUXTRONIK)
    if not luxtronik:
        return False

    sensors = config.get(CONF_SENSORS)

    entities = []
    for sensor_cfg in sensors:
        sensor = luxtronik.get_sensor(sensor_cfg["group"], sensor_cfg["id"])
        if sensor:
            entities.append(LuxtronikSensor(luxtronik, sensor, sensor_cfg))
        else:
            _LOGGER.warning(
                "Invalid Luxtronik ID %s in group %s",
                sensor_cfg["id"],
                sensor_cfg["group"],
            )

    add_entities(entities, True)


class LuxtronikSensor(Entity):
    """Representation of a Luxtronik sensor."""

    def __init__(self, luxtronik, sensor, sensor_cfg):
        """Initialize a new Luxtronik sensor."""
        self._luxtronik = luxtronik
        self._sensor = sensor
        self._name = sensor_cfg["friendly_name"]
        self._icon = sensor_cfg["icon"]
        self._state = None
        self._unit = None
        self._device_class = None
        self._category = None
        self._value = None

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
            return ENTITY_ID_FORMAT.format(slugify(self._sensor.name))
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if not self._icon:
            icons = {
                "celsius": "mdi:thermometer",
                "seconds": "mdi:timer-sand",
                "pulses": "mdi:pulse",
                "ipaddress": "mdi:ip-network-outline",
                "timestamp": "mdi:calendar-range",
                "errorcode": "mdi:alert-circle-outline",
                "kelvin": "mdi:thermometer",
                "bar": "mdi:arrow-collapse-all",
                "percent": "mdi:percent",
                "rpm": "mdi:rotate-right",
                "energy": "mdi:flash-circle",
                "voltage": "mdi:flash-outline",
                "hours": "mdi:clock-outline",
                "flow": "mdi:chart-bell-curve",
                "level": "mdi:format-list-numbered",
                "count": "mdi:counter",
                "version": "mdi:information-outline",
            }
            return icons.get(self._sensor.measurement_type, None)
        return self._icon

    @property
    def state(self):
        """Return the sensor state."""
        return self._sensor

    @property
    def device_class(self):
        """Return the class of this sensor."""
        device_classes = {
            "celsius": "temperature",
            "kelvin": "temperature",
            "pressure": "pressure",
            "seconds": "time",
            "hours": "time",
            "timestamp": "time",
        }
        return device_classes.get(self._sensor.measurement_type, DEFAULT_DEVICE_CLASS)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        units = {
            "celsius": "°C",
            "seconds": "s",
            "kelvin": "K",
            "bar": "bar",
            "percent": "%",
            "energy": "kWh",
            "voltage": "V",
            "hours": "h",
            "flow": "l/min",
        }
        return units.get(self._sensor.measurement_type, None)

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        self._luxtronik.update()
