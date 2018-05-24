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
from homeassistant.const import (STATE_OFF, STATE_ON)

DEPENDENCIES = ['tahoma']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tahoma controller devices."""
    _LOGGER.debug("Setup Tahoma Binary sensor platform")
    controller = hass.data[TAHOMA_DOMAIN]['controller']
    devices = []
    for device in hass.data[TAHOMA_DOMAIN]['devices']['smoke']:
        devices.append(TahomaBinarySensor(device, controller))
    add_devices(devices, True)


class TahomaBinarySensor(TahomaDevice, BinarySensorDevice):
    """Representation of a Tahoma Binary Sensor."""

    def __init__(self, tahoma_device, controller):
        """Initialize the sensor."""
        self._state = None
        super().__init__(tahoma_device, controller)

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
        if self.is_on:
            return "mdi:fire"

    def update(self):
        """Update the state."""
        self.controller.get_states([self.tahoma_device])
        if self.tahoma_device.type == 'rtds:RTDSSmokeSensor':
            if self.tahoma_device.active_states['core:SmokeState']\
                    == 'notDetected':
                self._state = STATE_OFF
            else:
                self._state = STATE_ON

        # FIXME: Check for low battery state.
        # self.tahoma_device.active_states['core:SensorDefectState'] ==
        #     'lowBattery' """
