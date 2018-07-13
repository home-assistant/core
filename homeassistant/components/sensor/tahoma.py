"""
Support for Tahoma sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tahoma/
"""

import logging
from datetime import timedelta

from homeassistant.helpers.entity import Entity
from homeassistant.components.tahoma import (
    DOMAIN as TAHOMA_DOMAIN, TahomaDevice)
from homeassistant.const import (ATTR_BATTERY_LEVEL)

DEPENDENCIES = ['tahoma']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)

ATTR_RSSI_LEVEL = 'rssi_level'
ATTR_STATUS = 'status'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tahoma controller devices."""
    controller = hass.data[TAHOMA_DOMAIN]['controller']
    devices = []
    for device in hass.data[TAHOMA_DOMAIN]['devices']['sensor']:
        devices.append(TahomaSensor(device, controller))
    add_devices(devices, True)


class TahomaSensor(TahomaDevice, Entity):
    """Representation of a Tahoma Sensor."""

    def __init__(self, tahoma_device, controller):
        """Initialize the sensor."""
        self.current_value = None
        super().__init__(tahoma_device, controller)

    @property
    def state(self):
        """Return the name of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self.tahoma_device.type == 'Temperature Sensor':
            return None
        elif self.tahoma_device.type == 'io:SomfyContactIOSystemSensor':
            return None
        elif self.tahoma_device.type == 'io:LightIOSystemSensor':
            return 'lx'
        elif self.tahoma_device.type == 'Humidity Sensor':
            return '%'

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        super_attr = super().device_state_attributes
        if super_attr is not None:
            attr.update(super_attr)

        if 'core:RSSILevelState' in self.tahoma_device.active_states:
            attr[ATTR_RSSI_LEVEL] = \
                self.tahoma_device.active_states['core:RSSILevelState']
        if 'core:SensorDefectState' in self.tahoma_device.active_states:
            attr[ATTR_BATTERY_LEVEL] = \
                self.tahoma_device.active_states['core:SensorDefectState']
        if 'core:StatusState' in self.tahoma_device.active_states:
            attr[ATTR_STATUS] = \
                self.tahoma_device.active_states['core:StatusState']
        return attr

    def update(self):
        """Update the state."""
        self.controller.get_states([self.tahoma_device])
        if self.tahoma_device.type == 'io:LightIOSystemSensor':
            self.current_value = self.tahoma_device.active_states[
                'core:LuminanceState']
        if self.tahoma_device.type == 'io:SomfyContactIOSystemSensor':
            self.current_value = self.tahoma_device.active_states[
                'core:ContactState']

        _LOGGER.debug("Update %s, value: %d", self._name, self.current_value)
