"""
This component provides HA binary_sensor support for Abode Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.abode/
"""
import logging

from homeassistant.components.abode import (
    AbodeDevice, ABODE_CONTROLLER)
from homeassistant.components.binary_sensor import (BinarySensorDevice)

DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)

# Sensor types: Name, device_class
SENSOR_TYPES = {
    'Door Contact': 'opening',
    'Motion Camera': 'motion',
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for an Abode device."""
    import abodepy.helpers.constants as CONST

    device_types = [
        CONST.DEVICE_GLASS_BREAK, CONST.DEVICE_KEYPAD,
        CONST.DEVICE_DOOR_CONTACT, CONST.DEVICE_STATUS_DISPLAY,
        CONST.DEVICE_MOTION_CAMERA, CONST.DEVICE_WATER_SENSOR]

    sensors = []
    for sensor in ABODE_CONTROLLER.get_devices(type_filter=device_types):
        sensors.append(AbodeBinarySensor(hass, ABODE_CONTROLLER, sensor))
        _LOGGER.debug('Added Binary Sensor %s', sensor.name)

    _LOGGER.debug('Adding %d Binary Snsors', len(sensors))

    add_devices(sensors)


def map_abode_device_class(abode_device):
    """Map Abode device types to Home Assistant binary sensor class."""
    import abodepy.helpers.constants as CONST

    if abode_device.type == CONST.DEVICE_GLASS_BREAK:
        return 'connectivity'
    elif abode_device.type == CONST.DEVICE_KEYPAD:
        return 'connectivity'
    elif abode_device.type == CONST.DEVICE_DOOR_CONTACT:
        return 'opening'
    elif abode_device.type == CONST.DEVICE_STATUS_DISPLAY:
        return 'connectivity'
    elif abode_device.type == CONST.DEVICE_MOTION_CAMERA:
        return 'motion'
    elif abode_device.type == CONST.DEVICE_WATER_SENSOR:
        return 'moisture'

    return None


class AbodeBinarySensor(AbodeDevice, BinarySensorDevice):
    """A binary sensor implementation for Abode device."""

    def __init__(self, hass, controller, device):
        """Initialize a sensor for Abode device."""
        AbodeDevice.__init__(self, hass, controller, device)

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        if self.device_class == 'motion':
            return self._device.get_value('motion_event') == '1'
        else:
            return self._device.is_on

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return map_abode_device_class(self._device)
