"""
Support for Vera locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.vera/
"""
import logging

from homeassistant.components.lock import LockDevice
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, STATE_LOCKED, STATE_UNLOCKED)
from homeassistant.components.vera import (
    VeraDevice, VERA_DEVICES, VERA_CONTROLLER)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Find and return Vera locks."""
    add_devices_callback(
        VeraLock(device, VERA_CONTROLLER) for
        device in VERA_DEVICES['lock'])


class VeraLock(VeraDevice, LockDevice):
    """Representation of a Vera lock."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        self._state = None
        VeraDevice.__init__(self, vera_device, controller)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level + '%'

        attr['Vera Device Id'] = self.vera_device.vera_device_id
        return attr

    def lock(self, **kwargs):
        """Lock the device."""
        self.vera_device.lock()
        self._state = STATE_LOCKED
        self.update_ha_state()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self.vera_device.unlock()
        self._state = STATE_UNLOCKED
        self.update_ha_state()

    @property
    def is_locked(self):
        """Return true if device is on."""
        return self._state == STATE_LOCKED

    def update(self):
        """Called by the Vera device callback to update state."""
        self._state = (STATE_LOCKED if self.vera_device.is_locked(True)
                       else STATE_UNLOCKED)
