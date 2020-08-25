"""Support for Goal Zero Yeti."""
import logging
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from requests import get, exceptions
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_BINARY_SENSORS,
    POWER_WATT,
    ENERGY_WATT_HOUR,
    ATTR_VOLTAGE,
    TEMP_CELSIUS,
    TIME_MINUTES,
    TIME_SECONDS,
    UNIT_PERCENTAGE,
)

_LOGGER = logging.getLogger(__name__)
_THROTTLED_REFRESH = None

PLATFORMS = ["binary_sensor", "sensor"]

SENSOR_TYPES = {
    "thingName": ["Name", CONF_NAME],
    "backlight": ["Backlight", CONF_BINARY_SENSORS],
    "app_online": ["App Online", CONF_BINARY_SENSORS],
    "wattsIn": ["Watts In", POWER_WATT],
    "ampsIn": ["Amps In", "A"],
    "wattsOut": ["Watts Out", POWER_WATT],
    "ampsOut": ["Amps Out", "A"],
    "whOut": ["Wh Out", ENERGY_WATT_HOUR],
    "whStored": ["Wh Stored", ENERGY_WATT_HOUR],
    "volts": ["Volts", ATTR_VOLTAGE],
    "socPercent": ["State of Charge Percent", UNIT_PERCENTAGE],
    "isCharging": ["Is Charging", CONF_BINARY_SENSORS],
    "timeToEmptyFull": ["Time to Empty/Full", TIME_MINUTES],
    "temperature": ["temperature", TEMP_CELSIUS],
    "wifiStrength": ["Wifi Strength", "dB"],
    "timestamp": ["Time Stamp", TIME_SECONDS],
    "firmwareVersion": ["Firmware Version", None],
    "version": ["Model Version", None],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.matches_regex(
            r"\A(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2 \
            [0-4][0-9]|[01]?[0-9][0-9]?)\Z"
        ),
        vol.Optional(CONF_NAME, default="Yeti"): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Goal Zero Yeti sensors."""

    name = config[CONF_NAME]
    host = config[CONF_HOST]

    try:
        response = get("http://" + host + "/state", timeout=10).json()
    except exceptions.MissingSchema:
        _LOGGER.error("Missing host or schema in configuration")
        return False
    except exceptions.ConnectionError:
        _LOGGER.error("No route to device at %s", host)
        return False
    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(YetiSensor(variable, response, name))

    add_entities(dev)


class YetiSensor(Entity):
    """Representation of a Goal Zero Yeti sensor."""

    def __init__(self, sensor_type, response, client_name):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.data = response
        self._available = True

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return true if device is available."""
        return self._available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from Goal Zero Yeti and updates the state."""

        if self.data:
            self._available = True
            for variable in self.data:
                if self.type == variable:
                    self._state = self.data[variable]
        else:
            self._available = False
