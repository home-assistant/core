"""
This component provides HA binary_sensor support for Tesla.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.tesla/
"""
import logging
from homeassistant.components.binary_sensor import BinarySensorDevice, \
    ENTITY_ID_FORMAT
from homeassistant.components.tesla import (
    TESLA_CONTROLLER, TESLA_DEVICES, TeslaDevice)

DEPENDENCIES = ['tesla']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tesla binary sensor."""
    devices = [TeslaBinarySensor(device, TESLA_CONTROLLER, 'connectivity')
               for device in TESLA_DEVICES['binary_sensor']]
    add_devices(devices, True)


class TeslaBinarySensor(TeslaDevice, BinarySensorDevice):
    """Implement an Tesla binary sensor for parking and charger."""

    def __init__(self, tesla_device, controller, sensor_type):
        """Initialisation of binary sensor."""
        TeslaDevice.__init__(self, tesla_device, controller)
        self._name = self.tesla_device.name
        self._state = False
        self.entity_id = ENTITY_ID_FORMAT.format(self.tesla_id)
        self._sensor_type = sensor_type

    @property
    def device_class(self):
        """Return the class of this binary sensor."""
        return self._sensor_type

    @property
    def should_poll(self):
        """Should be polled."""
        return True

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state

    def update(self):
        """Update the state of the device."""
        _LOGGER.debug('Updating sensor: {}'.format(self._name))
        self.tesla_device.update()
        self._state = self.tesla_device.get_value()
