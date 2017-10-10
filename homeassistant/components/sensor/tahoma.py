"""
Support for Tahoma sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tahoma/
"""

import logging
from datetime import timedelta

from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.components.tahoma import (TahomaDevice)

DEPENDENCIES = ['tahoma']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tahoma controller devices."""
    add_devices(
        TahomaSensor(device, hass.data['TAHOMA_CONTROLLER'])
        for device in hass.data['tahomasensor'])


class TahomaSensor(TahomaDevice, Entity):
    """Representation of a Tahoma Sensor."""

    def __init__(self, tahoma_device, controller):
        """Initialize the sensor."""
        self.current_value = None
        self._temperature_units = None
        self.last_changed_time = None
        TahomaDevice.__init__(self, tahoma_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.tahoma_id)

    @property
    def state(self):
        """Return the name of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self.tahoma_device.type == 'Temperature Sensor':
            return self._temperature_units
        elif self.tahoma_device.type == 'io:LightIOSystemSensor':
            return 'lux'
        elif self.tahoma_device.type == 'Humidity Sensor':
            return '%'

    def update(self):
        """Update the state."""
        self.controller.get_states([self.tahoma_device])
        if self.tahoma_device.type == 'io:LightIOSystemSensor':
            _val = self.tahoma_device.active_states['core:LuminanceState']
            self.current_value = _val

        self.schedule_update_ha_state()
