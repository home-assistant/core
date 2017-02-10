"""
Support for Wink locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.wink/
"""

from homeassistant.components.lock import LockDevice
from homeassistant.components.wink import WinkDevice, DOMAIN

DEPENDENCIES = ['wink']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink platform."""
    import pywink

    for lock in pywink.get_locks():
        _id = lock.object_id() + lock.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkLockDevice(lock, hass)])


class WinkLockDevice(WinkDevice, LockDevice):
    """Representation of a Wink lock."""

    def __init__(self, wink, hass):
        """Initialize the lock."""
        super().__init__(wink, hass)

    @property
    def is_locked(self):
        """Return true if device is locked."""
        return self.wink.state()

    def lock(self, **kwargs):
        """Lock the device."""
        self.wink.set_state(True)

    def unlock(self, **kwargs):
        """Unlock the device."""
        self.wink.set_state(False)
