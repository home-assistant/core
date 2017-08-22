"""
This component provides HA cover support for Abode Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.abode/
"""
import logging

from homeassistant.components.abode import (
    AbodeDevice, ABODE_CONTROLLER)
from homeassistant.components.cover import CoverDevice

DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Abode cover devices."""
    import abodepy.helpers.constants as CONST

    sensors = []

    for sensor in ABODE_CONTROLLER.get_devices(
            type_filter=(CONST.DEVICE_SECURE_BARRIER)):
        sensors.append(AbodeCover(hass, ABODE_CONTROLLER, sensor))
        _LOGGER.debug('Added Cover %s', sensor.name)

    _LOGGER.debug('Adding %d Covers', len(sensors))
    add_devices(sensors)


class AbodeCover(AbodeDevice, CoverDevice):
    """Representation of an Abode cover."""

    def __init__(self, hass, controller, device):
        """Initialize the Abode device."""
        AbodeDevice.__init__(self, hass, controller, device)

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self._device.is_open is False

    def close_cover(self):
        """Issue close command to cover."""
        self._device.switch_off()

    def open_cover(self):
        """Issue open command to cover."""
        self._device.switch_on()
