"""Support for Vera binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT, BinarySensorDevice)

from . import VERA_CONTROLLER, VERA_DEVICES, VeraDevice

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Vera controller devices."""
    add_entities(
        [VeraBinarySensor(device, hass.data[VERA_CONTROLLER])
         for device in hass.data[VERA_DEVICES]['binary_sensor']], True)


class VeraBinarySensor(VeraDevice, BinarySensorDevice):
    """Representation of a Vera Binary Sensor."""

    def __init__(self, vera_device, controller):
        """Initialize the binary_sensor."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and update the state."""
        self._state = self.vera_device.is_tripped
