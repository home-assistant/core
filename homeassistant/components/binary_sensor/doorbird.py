"""
Support for reading binary states from a DoorBird video doorbell.
"""
from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice,\
    PLATFORM_SCHEMA
from homeassistant.components.doorbird import DOMAIN
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_MONITORED_CONDITIONS, STATE_UNKNOWN
from homeassistant.util import Throttle

DEPENDENCIES = ['doorbird']

_LOGGER = logging.getLogger(__name__)
_MIN_UPDATE_INTERVAL = timedelta(milliseconds=250)

SENSOR_TYPES = {
    "doorbell": {
        "name": "Doorbell Ringing",
        "icon": {
            True: "bell-ring",
            False: "bell",
            STATE_UNKNOWN: "bell-outline"
        }
    }
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list([vol.In(SENSOR_TYPES)]))
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    device = hass.data.get(DOMAIN)

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        if sensor_type == "doorbell":
            _LOGGER.debug("Adding DoorBird binary sensor " +
                          str(SENSOR_TYPES[sensor_type]["name"]))
            sensors.append(DoorBirdBinarySensor(device, sensor_type))

    add_devices(sensors, True)
    _LOGGER.info("Added DoorBird binary sensors")
    return True


class DoorBirdBinarySensor(BinarySensorDevice):
    def __init__(self, device, sensor_type):
        """Initialize a binary sensor on a DoorBird device."""
        if sensor_type not in SENSOR_TYPES:
            msg = sensor_type + " is not a valid DoorBird binary sensor"
            raise NotImplementedError(msg)

        self._device = device
        self._sensor_type = sensor_type
        self._state = STATE_UNKNOWN
        super(DoorBirdBinarySensor, self).__init__()

    @property
    def name(self):
        """:returns: The name of the sensor."""
        return SENSOR_TYPES[self._sensor_type]["name"]

    @property
    def icon(self):
        """:returns: An icon to display."""
        icon = SENSOR_TYPES[self._sensor_type]["icon"][self._state]
        return "mdi:" + str(icon)

    @property
    def is_on(self):
        """:returns: The state of the binary sensor."""
        return self._state

    @Throttle(_MIN_UPDATE_INTERVAL)
    def update(self):
        """Pulls the latest value from the device."""
        self._state = self._device.doorbell_state()
