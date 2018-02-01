"""
Support for Vera locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.vera/
"""
import logging

from homeassistant.components.lock import ENTITY_ID_FORMAT, LockDevice
from homeassistant.const import (STATE_LOCKED, STATE_UNLOCKED)
from homeassistant.components.vera import (
    VERA_CONTROLLER, VERA_DEVICES, VeraDevice)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['vera']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Vera locks."""
    add_devices(
        VeraLock(device, hass.data[VERA_CONTROLLER]) for
        device in hass.data[VERA_DEVICES]['lock'])


class VeraLock(VeraDevice, LockDevice):
    """Representation of a Vera lock."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        self._state = None
        VeraDevice.__init__(self, vera_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    def lock(self, **kwargs):
        """Lock the device."""
        self.vera_device.lock()
        self._state = STATE_LOCKED

    def unlock(self, **kwargs):
        """Unlock the device."""
        self.vera_device.unlock()
        self._state = STATE_UNLOCKED

    @property
    def is_locked(self):
        """Return true if device is on."""
        return self._state == STATE_LOCKED

    def update(self):
        """Update state by the Vera device callback."""
        self._state = (STATE_LOCKED if self.vera_device.is_locked(True)
                       else STATE_UNLOCKED)
