"""
homeassistant.components.sensor.temper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Support for getting temperature from TEMPer devices
"""

import logging
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Temper sensors. """
    try:
        # pylint: disable=no-name-in-module, import-error
        from temperusb.temper import TemperHandler
    except ImportError:
        _LOGGER.error('Failed to import temperusb')
        return False

    temp_unit = hass.config.temperature_unit
    temper_devices = TemperHandler().get_devices()
    add_devices_callback([TemperSensor(dev, temp_unit) for dev in temper_devices])


class TemperSensor(Entity):
    def __init__(self, temper_device, temp_unit):
        self.temper_device = temper_device
        self.temp_unit = temp_unit
        self.current_value = None

    @property
    def state(self):
        """ Returns the state of the entity. """
        return self.current_value

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity, if any. """
        return self.temp_unit

    def update(self):
        """ Retrieve latest state. """
        try:
            self.current_value = self.temper_device.get_temperature()
        except Exception:
            _LOGGER.error('Failed to get temperature due to insufficient permissions')
