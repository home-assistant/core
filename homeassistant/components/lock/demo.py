"""
homeassistant.components.lock.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demo platform that has two fake locks.
"""
from homeassistant.components.lock import LockDevice
from homeassistant.const import (
    DEVICE_DEFAULT_NAME, STATE_LOCKED, STATE_UNLOCKED)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return demo locks. """
    add_devices_callback([
        DemoLock('Left Door', STATE_LOCKED, None),
        DemoLock('Right Door', STATE_UNLOCKED, None)
    ])


class DemoLock(LockDevice):
    """ Provides a demo lock. """
    def __init__(self, name, state, icon):
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self._icon = icon

    @property
    def should_poll(self):
        """ No polling needed for a demo lock. """
        return False

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def icon(self):
        """ Returns the icon to use for device if any. """
        return self._icon

    @property
    def is_locked(self):
        """ True if device is locked. """
        if self._state == STATE_LOCKED:
            return True
        else:
            return False

    def lock(self, **kwargs):
        """ Lock the device. """
        self._state = STATE_LOCKED
        self.update_ha_state()

    def unlock(self, **kwargs):
        """ Unlock the device. """
        self._state = STATE_UNLOCKED
        self.update_ha_state()
