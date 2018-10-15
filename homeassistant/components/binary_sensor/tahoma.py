"""
Support for Tahoma binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.tahoma/
"""

import logging
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDevice)
from homeassistant.components.tahoma import (
    DOMAIN as TAHOMA_DOMAIN, TahomaDevice)
from homeassistant.const import (STATE_OFF, STATE_ON, ATTR_BATTERY_LEVEL)

DEPENDENCIES = ['tahoma']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Tahoma controller devices."""
    _LOGGER.debug("Setup Tahoma Binary sensor platform")
    controller = hass.data[TAHOMA_DOMAIN]['controller']
    devices = []
    for device in hass.data[TAHOMA_DOMAIN]['devices']['smoke']:
        devices.append(TahomaBinarySensor(device, controller))
    add_entities(devices, True)


class TahomaBinarySensor(TahomaDevice, BinarySensorDevice):
    """Representation of a Tahoma Binary Sensor."""

    def __init__(self, tahoma_device, controller):
        """Initialize the sensor."""
        super().__init__(tahoma_device, controller)

        self._state = None
        self._icon = None
        self._battery = None

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return bool(self._state == STATE_ON)

    @property
    def device_class(self):
        """Return the class of the device."""
        if self.tahoma_device.type == 'rtds:RTDSSmokeSensor':
            return 'smoke'
        return None

    @property
    def icon(self):
        """Icon for device by its type."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        super_attr = super().device_state_attributes
        if super_attr is not None:
            attr.update(super_attr)

        if self._battery is not None:
            attr[ATTR_BATTERY_LEVEL] = self._battery
        return attr

    def update(self):
        """Update the state."""
        self.controller.get_states([self.tahoma_device])
        if self.tahoma_device.type == 'rtds:RTDSSmokeSensor':
            if self.tahoma_device.active_states['core:SmokeState']\
                    == 'notDetected':
                self._state = STATE_OFF
            else:
                self._state = STATE_ON

        if 'core:SensorDefectState' in self.tahoma_device.active_states:
            # Set to 'lowBattery' for low battery warning.
            self._battery = self.tahoma_device.active_states[
                'core:SensorDefectState']
        else:
            self._battery = None

        if self._state == STATE_ON:
            self._icon = "mdi:fire"
        elif self._battery == 'lowBattery':
            self._icon = "mdi:battery-alert"
        else:
            self._icon = None

        _LOGGER.debug("Update %s, state: %s", self._name, self._state)
