"""
This component provides HA cover support for Abode Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.abode/
"""
import logging

from homeassistant.components.abode import AbodeDevice, DATA_ABODE
from homeassistant.components.cover import CoverDevice


DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Abode cover devices."""
    import abodepy.helpers.constants as CONST

    abode = hass.data[DATA_ABODE]

    sensors = []
    for sensor in abode.get_devices(type_filter=(CONST.DEVICE_SECURE_BARRIER)):
        sensors.append(AbodeCover(abode, sensor))

    add_devices(sensors)


class AbodeCover(AbodeDevice, CoverDevice):
    """Representation of an Abode cover."""

    def __init__(self, controller, device):
        """Initialize the Abode device."""
        AbodeDevice.__init__(self, controller, device)

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self._device.is_open is False

    def close_cover(self):
        """Issue close command to cover."""
        self._device.close_cover()

    def open_cover(self):
        """Issue open command to cover."""
        self._device.open_cover()
