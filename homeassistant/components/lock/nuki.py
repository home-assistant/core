"""
Nuki.io lock platform.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/lock.nuki/
"""
from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.lock import (LockDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_TOKEN)
from homeassistant.util import Throttle

REQUIREMENTS = ['pynuki==1.2.2']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8080

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_TOKEN): cv.string
})


MIN_TIME_BETWEEN_SCANS = timedelta(seconds=30)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=5)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Nuki lock platform."""
    from pynuki import NukiBridge
    bridge = NukiBridge(config.get(CONF_HOST), config.get(CONF_TOKEN))
    add_devices([NukiLock(lock) for lock in bridge.locks])


class NukiLock(LockDevice):
    """Representation of a Nuki lock."""

    def __init__(self, nuki_lock):
        """Initialize the lock."""
        self._nuki_lock = nuki_lock
        self._locked = nuki_lock.is_locked
        self._name = nuki_lock.name

    @property
    def name(self):
        """Return the name of the lock."""
        return self._name

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._locked

    @Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Update the nuki lock properties."""
        self._nuki_lock.update(aggressive=False)
        self._name = self._nuki_lock.name
        self._locked = self._nuki_lock.is_locked

    def lock(self, **kwargs):
        """Lock the device."""
        self._nuki_lock.lock()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._nuki_lock.unlock()
