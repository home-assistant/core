"""
Support for Volvo On Call locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.volvooncall/
"""
import logging

from homeassistant.components.lock import LockDevice
from homeassistant.components.volvooncall import VolvoEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Volvo On Call lock."""
    if discovery_info is None:
        return

    add_devices([VolvoLock(hass, *discovery_info)])


class VolvoLock(VolvoEntity, LockDevice):
    """Represents a car lock."""

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self.vehicle.is_locked

    def lock(self, **kwargs):
        """Lock the car."""
        self.vehicle.lock()

    def unlock(self, **kwargs):
        """Unlock the car."""
        self.vehicle.unlock()
