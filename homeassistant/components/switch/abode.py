"""
This component provides HA switch support for Abode Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.abode/
"""
import logging

from homeassistant.components.abode import (
    AbodeDevice, ABODE_CONTROLLER)
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Abode switch devices."""
    import abodepy.helpers.constants as CONST

    sensors = []

    for sensor in ABODE_CONTROLLER.get_devices(
            type_filter=(CONST.DEVICE_POWER_SWITCH)):
        sensors.append(AbodeSwitch(hass, ABODE_CONTROLLER, sensor))
        _LOGGER.debug('Added Switch %s', sensor.name)

    _LOGGER.debug('Adding %d Switches', len(sensors))
    add_devices(sensors)


class AbodeSwitch(AbodeDevice, SwitchDevice):
    """Representation of an Abode switch."""

    def __init__(self, hass, controller, device):
        """Initialize the Abode device."""
        AbodeDevice.__init__(self, hass, controller, device)

    def turn_on(self, **kwargs):
        """Turn on the device."""
        self._device.switch_on()

    def turn_off(self, **kwargs):
        """Turn off the device."""
        self._device.switch_off()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.is_on
