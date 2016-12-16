"""
Demo lock platform that has two fake locks.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.lock import LockDevice
from homeassistant.const import (STATE_LOCKED, STATE_UNLOCKED)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo lock platform."""
    add_devices([
        DemoLock('Front Door', STATE_LOCKED),
        DemoLock('Kitchen Door', STATE_UNLOCKED)
    ])


class DemoLock(LockDevice):
    """Representation of a Demo lock."""

    def __init__(self, name, state):
        """Initialize the lock."""
        self._name = name
        self._state = state

    @property
    def should_poll(self):
        """No polling needed for a demo lock."""
        return False

    @property
    def name(self):
        """Return the name of the lock if any."""
        return self._name

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state == STATE_LOCKED

    def lock(self, **kwargs):
        """Lock the device."""
        self._state = STATE_LOCKED
        self.update_ha_state()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._state = STATE_UNLOCKED
        self.update_ha_state()
