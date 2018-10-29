"""
This component provides HA binary_sensor support for Lupusec Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.lupusec/
"""
import logging

from homeassistant.components.lupusec import (LupusecDevice,
                                              DOMAIN as LUPUSEC_DOMAIN)
from homeassistant.components.lupusec import SCAN_INTERVAL as SCAN_INTERVAL
from homeassistant.components.binary_sensor import BinarySensorDevice

DEPENDENCIES = ['lupusec']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for an Lupusec device."""
    import lupupy.constants as CONST

    data = hass.data[LUPUSEC_DOMAIN]

    device_types = [CONST.TYPE_OPENING]

    devices = []
    for device in data.lupusec.get_devices(generic_type=device_types):
        devices.append(LupusecBinarySensor(data, device))

    data.devices.extend(devices)
    add_entities(devices)


class LupusecBinarySensor(LupusecDevice, BinarySensorDevice):
    """A binary sensor implementation for Lupusec device."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._device.is_on

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device.type
