"""Support for MyChevy sensors."""

from logging import getLogger
from datetime import datetime as dt
from datetime import timedelta
import time
import threading

from homeassistant.components.mychevy import (
    EVBinarySensorConfig, DOMAIN, MYCHEVY_ERROR, MYCHEVY_SUCCESS,
    NOTIFICATION_ID, NOTIFICATION_TITLE
)
from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT, BinarySensorDevice)
from homeassistant.helpers.entity import Entity
from homeassistant.util import (Throttle, slugify)

_LOGGER = getLogger(__name__)

SENSORS = [
    EVBinarySensorConfig("Plugged In", "plugged_in", "plug")
]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MyChevy sensors."""
    if discovery_info is None:
        return

    sensors = []
    hub = hass.data[DOMAIN]
    for sconfig in SENSORS:
        sensors.append(EVBinarySensor(hub, sconfig))

    add_devices(sensors)



class EVBinarySensor(BinarySensorDevice):
    """Base EVSensor class.

    The only real difference between sensors is which units and what
    attribute from the car object they are returning. All logic can be
    built with just setting subclass attributes.

    """
    def __init__(self, connection, config):
        """Initialize sensor with car connection."""
        self._conn = connection
        connection.sensors.append(self)
        self.car = connection.car
        self._name = config.name
        self._attr = config.attr
        self._type = config.device_class

        self.entity_id = ENTITY_ID_FORMAT.format(
            '{}_{}'.format(DOMAIN, slugify(self._name)))

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def is_on(self):
        """Return if on."""
        if self.car is not None:
            return getattr(self.car, self._attr, None)

    @property
    def hidden(self):
        if self.car == None:
            return True
        return False

    @property
    def should_poll(self):
        """Return the polling state."""
        return False
