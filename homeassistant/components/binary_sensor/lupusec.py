"""
This component provides HA binary_sensor support for Lupusec Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.lupusec/
"""
import logging
from datetime import timedelta

from homeassistant.components.lupusec import (LupusecDevice,
                                              DOMAIN as LUPUSEC_DOMAIN)
from homeassistant.components.binary_sensor import (BinarySensorDevice,
                                                    DEVICE_CLASSES)

DEPENDENCIES = ['lupusec']

SCAN_INTERVAL = timedelta(seconds=2)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for an Lupusec device."""
    if discovery_info is None:
        return

    import lupupy.constants as CONST

    data = hass.data[LUPUSEC_DOMAIN]

    device_types = [CONST.TYPE_OPENING]

    devices = []
    for device in data.lupusec.get_devices(generic_type=device_types):
        devices.append(LupusecBinarySensor(data, device))

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
        if self._device.generic_type not in DEVICE_CLASSES:
            return None
        return self._device.generic_type
