"""
Demo lock platform that has two fake locks.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED

from homeassistant.components.lock import SUPPORT_OPEN, LockDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo lock platform."""
    add_entities([
        DemoLock('Front Door', STATE_LOCKED),
        DemoLock('Kitchen Door', STATE_UNLOCKED),
        DemoLock('Openable Lock', STATE_LOCKED, True)
    ])


class DemoLock(LockDevice):
    """Representation of a Demo lock."""

    def __init__(self, name, state, openable=False):
        """Initialize the lock."""
        self._name = name
        self._state = state
        self._openable = openable

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
        self.schedule_update_ha_state()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._state = STATE_UNLOCKED
        self.schedule_update_ha_state()

    def open(self, **kwargs):
        """Open the door latch."""
        self._state = STATE_UNLOCKED
        self.schedule_update_ha_state()

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._openable:
            return SUPPORT_OPEN
