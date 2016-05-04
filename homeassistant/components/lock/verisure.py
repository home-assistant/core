"""
Interfaces with Verisure locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/verisure/
"""
import logging

from homeassistant.components.verisure import HUB as hub
from homeassistant.components.lock import LockDevice
from homeassistant.const import (
    ATTR_CODE, STATE_LOCKED, STATE_UNKNOWN, STATE_UNLOCKED)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Verisure platform."""
    locks = []
    if int(hub.config.get('locks', '1')):
        hub.update_locks()
        locks.extend([
            VerisureDoorlock(device_id)
            for device_id in hub.lock_status.keys()
        ])
    add_devices(locks)


# pylint: disable=abstract-method
class VerisureDoorlock(LockDevice):
    """Representation of a Verisure doorlock."""

    def __init__(self, device_id):
        """Initialize the lock."""
        self._id = device_id
        self._state = STATE_UNKNOWN
        self._digits = int(hub.config.get('code_digits', '4'))

    @property
    def name(self):
        """Return the name of the lock."""
        return 'Lock {}'.format(self._id)

    @property
    def state(self):
        """Return the state of the lock."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return hub.available

    @property
    def code_format(self):
        """Return the required six digit code."""
        return '^\\d{%s}$' % self._digits

    def update(self):
        """Update lock status."""
        hub.update_locks()

        if hub.lock_status[self._id].status == 'unlocked':
            self._state = STATE_UNLOCKED
        elif hub.lock_status[self._id].status == 'locked':
            self._state = STATE_LOCKED
        elif hub.lock_status[self._id].status != 'pending':
            _LOGGER.error(
                'Unknown lock state %s',
                hub.lock_status[self._id].status)

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return hub.lock_status[self._id].status

    def unlock(self, **kwargs):
        """Send unlock command."""
        hub.my_pages.lock.set(kwargs[ATTR_CODE], self._id, 'UNLOCKED')
        _LOGGER.info('verisure doorlock unlocking')
        hub.my_pages.lock.wait_while_pending()
        self.update()

    def lock(self, **kwargs):
        """Send lock command."""
        hub.my_pages.lock.set(kwargs[ATTR_CODE], self._id, 'LOCKED')
        _LOGGER.info('verisure doorlock locking')
        hub.my_pages.lock.wait_while_pending()
        self.update()
