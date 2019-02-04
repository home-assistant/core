"""
This component provides HA lock support for Abode Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.abode/
"""
import logging

from homeassistant.components.abode import AbodeDevice, DOMAIN as ABODE_DOMAIN
from homeassistant.components.lock import LockDevice


DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Abode lock devices."""
    import abodepy.helpers.constants as CONST

    data = hass.data[ABODE_DOMAIN]

    devices = []
    for device in data.abode.get_devices(generic_type=CONST.TYPE_LOCK):
        if data.is_excluded(device):
            continue

        devices.append(AbodeLock(data, device))

    data.devices.extend(devices)

    add_entities(devices)


class AbodeLock(AbodeDevice, LockDevice):
    """Representation of an Abode lock."""

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
