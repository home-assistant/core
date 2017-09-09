"""
This component provides HA lock support for Abode Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.abode/
"""
import logging

from homeassistant.components.abode import AbodeDevice, DATA_ABODE
from homeassistant.components.lock import LockDevice


DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Abode lock devices."""
    import abodepy.helpers.constants as CONST

    abode = hass.data[DATA_ABODE]

    sensors = []
    for sensor in abode.get_devices(type_filter=(CONST.DEVICE_DOOR_LOCK)):
        sensors.append(AbodeLock(abode, sensor))

    add_devices(sensors)


class AbodeLock(AbodeDevice, LockDevice):
    """Representation of an Abode lock."""

    def __init__(self, controller, device):
        """Initialize the Abode device."""
        AbodeDevice.__init__(self, controller, device)

    def lock(self, **kwargs):
        """Lock the device."""
        self._device.lock()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._device.unlock()

    @property
    def is_locked(self):
        """Return true if device is on."""
        return self._device.is_locked
