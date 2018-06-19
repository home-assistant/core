"""
Provides a sensor to track the battery level of a Turn Touch remote.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.turn_touch/
"""

import logging

from homeassistant.const import DEVICE_CLASS_BATTERY
from homeassistant.components.turn_touch import DATA_KEY
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['turn_touch']

SENSOR_NAME = '{remote_name} Battery'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Turn Touch remote battery sensor platform."""
    devices = []
    for turntouch_device in hass.data[DATA_KEY]['devices'].values():
        devices.append(TurnTouchBatterySensor(turntouch_device))
    add_devices(devices, update_before_add=True)


class TurnTouchBatterySensor(Entity):
    """Representation of a Turn Touch remote's battery."""

    def __init__(self, turntouch_device):
        """
        Initialize the Turn Touch battery level sensor.

        This expects that the remote has already been initialized by the
        turn_touch component.
        """
        _LOGGER.debug('Initializing turn touch battery sensor.')
        self.turn_touch = turntouch_device
        self._battery_level = None

    @property
    def name(self):
        """Return the name of this sensor."""
        return SENSOR_NAME.format(remote_name=self.turn_touch.name)

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._battery_level

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return '%'

    @property
    def unique_id(self):
        """Return the Unique ID (based on MAC address) of this remote."""
        return self.turn_touch.address

    def update(self):
        """Get the latest data and updates the states."""
        self._battery_level = self.turn_touch.get_battery()
