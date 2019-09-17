"""Support for Abode Security System locks."""
import logging

from homeassistant.components.lock import LockDevice

from . import AbodeDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """This platform uses config entries."""
    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up Abode lock devices."""
    import abodepy.helpers.constants as CONST

    data = hass.data[DOMAIN]

    devices = []
    for device in data.abode.get_devices(generic_type=CONST.TYPE_LOCK):
        if data.is_excluded(device):
            continue

        devices.append(AbodeLock(data, device))

    async_add_devices(devices)


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
