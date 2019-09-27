"""
Support for monitoring the state of a Luxtronik heatpump.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.luxtronik/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_ICON, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from . import CONF_SENSORS, CONF_ID, DATA_LUXTRONIK, ENTITY_ID_FORMAT

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): vol.All(
            cv.ensure_list,
            [
                {
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
    for sensor in sensors:
        if luxtronik.valid_sensor_id(sensor["id"]):
            entities.append(LuxtronikSensor(luxtronik, sensor))
        else:
            _LOGGER.warning("Invalid Luxtronik ID %s", sensor["id"])

    add_entities(entities, True)


class LuxtronikSensor(Entity):
    """Representation of a Luxtronik sensor."""

    def __init__(self, luxtronik, sensor):
        """Initialize a new Luxtronik sensor."""
        self._luxtronik = luxtronik
        self._sensor = sensor["id"]
        self._name = sensor["friendly_name"]
        self._icon = sensor["icon"]
        self._state = None
        self._unit = None
        self._device_class = None
        self._data = None
        self._category = None
        self._value = None

    @property
    def entity_id(self):
        """Return the entity_id of the sensor."""
        if not self._name:
            return ENTITY_ID_FORMAT.format(slugify(self._sensor))
        return ENTITY_ID_FORMAT.format(slugify(self._name))

    @property
    def name(self):
        """Return the name of the sensor."""
        if not self._name:
            return ENTITY_ID_FORMAT.format(slugify(self._sensor))
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if not self._icon:
            icons = {
                "celsius": "mdi:thermometer",
                "pulses": "mdi:pulse",
                "seconds": "mdi:timer-sand",
                "info": "mdi:information-outline",
                "ipaddress": "mdi:ip-network-outline",
                "datetime": "mdi:calendar-range",
                "errorcode": "mdi:alert-circle-outline",
                "volt": "mdi:flash-outline",
                "percent": "mdi:percent",
                "rpm": "mdi:rotate-right",
                "kelvin": "mdi:thermometer",
                "bar": "mdi:arrow-collapse-all",
                "kWh": "mdi:flash-circle",
            }
            return icons.get(self._data["unit"])
        return self._icon

    @property
    def state(self):
        """Return the sensor state."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor."""
        device_classes = {
            "celsius": "temperature",
            "kelvin": "temperature",
            "pressure": "pressure",
        }
        return device_classes.get(self._data["unit"])

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        units = {
            "celsius": TEMP_CELSIUS,
            "kelvin": "K",
            "bar": "bar",
            "seconds": "s",
            "pulses": "pulses",
            "percent": "%",
            "rpm": "rpm",
            "kWh": "kWh",
            "volt": "V",
        }
        return units.get(self._data["unit"], None)

    def _locate_sensor(self, data):
        """Locate the sensor within the data structure."""
        for category in data:
            for value in data[category]:
                if data[category][value]["id"] == self._sensor:
                    self._category = category
                    self._value = value

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        self._luxtronik.update()
        data = self._luxtronik.data
        if not self._category or not self._value:
            self._locate_sensor(data)
        self._state = data[self._category][self._value]["value"]
        self._data = data[self._category][self._value]
