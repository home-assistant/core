"""Support for reading binary states from a DoorBird video doorbell."""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.doorbird import DOMAIN
from homeassistant.const import  STATE_UNKNOWN
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


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the DoorBird binary sensor component."""
    device = hass.data.get(DOMAIN)
    add_devices([DoorBirdBinarySensor(device, "doorbell")], True)
    return True


class DoorBirdBinarySensor(BinarySensorDevice):
    """A binary sensor of a DoorBird device."""
    def __init__(self, device, sensor_type):
        """Initialize a binary sensor on a DoorBird device."""
        self._device = device
        self._sensor_type = sensor_type
        self._state = STATE_UNKNOWN
        super(DoorBirdBinarySensor, self).__init__()

    @property
    def name(self):
        """Get the name of the sensor."""
        return SENSOR_TYPES[self._sensor_type]["name"]

    @property
    def icon(self):
        """Get an icon to display."""
        icon = SENSOR_TYPES[self._sensor_type]["icon"][self._state]
        return "mdi:{}".format(icon)

    @property
    def is_on(self):
        """Get the state of the binary sensor."""
        return self._state

    @Throttle(_MIN_UPDATE_INTERVAL)
    def update(self):
        """Pull the latest value from the device."""
        self._state = self._device.doorbell_state()
