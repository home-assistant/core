"""
Support for Vera binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.vera/
"""
import logging

import homeassistant.util.dt as dt_util
from homeassistant.const import (
    ATTR_ARMED, ATTR_BATTERY_LEVEL, ATTR_LAST_TRIP_TIME, ATTR_TRIPPED)
from homeassistant.components.binary_sensor import (
    BinarySensorDevice)
from homeassistant.components.vera import (
    VeraDevice, VERA_DEVICES, VERA_CONTROLLER)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Perform the setup for Vera controller devices."""
    add_devices_callback(
        VeraBinarySensor(device, VERA_CONTROLLER)
        for device in VERA_DEVICES['binary_sensor'])


class VeraBinarySensor(VeraDevice, BinarySensorDevice):
    """Representation of a Vera Binary Sensor."""

    def __init__(self, vera_device, controller):
        """Initialize the binary_sensor."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level + '%'

        if self.vera_device.is_armable:
            armed = self.vera_device.is_armed
            attr[ATTR_ARMED] = 'True' if armed else 'False'

        if self.vera_device.is_trippable:
            last_tripped = self.vera_device.last_trip
            if last_tripped is not None:
                utc_time = dt_util.utc_from_timestamp(int(last_tripped))
                attr[ATTR_LAST_TRIP_TIME] = utc_time.isoformat()
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
            tripped = self.vera_device.is_tripped
            attr[ATTR_TRIPPED] = 'True' if tripped else 'False'

        attr['Vera Device Id'] = self.vera_device.vera_device_id
        return attr

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and update the state."""
        self._state = self.vera_device.is_tripped
