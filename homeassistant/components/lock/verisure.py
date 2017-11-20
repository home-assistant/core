"""
Interfaces with Verisure locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/verisure/
"""
import logging
from time import sleep
from time import time
from homeassistant.components.verisure import HUB as hub
from homeassistant.components.verisure import (CONF_LOCKS, CONF_CODE_DIGITS)
from homeassistant.components.lock import LockDevice
from homeassistant.const import (
    ATTR_CODE, STATE_LOCKED, STATE_UNKNOWN, STATE_UNLOCKED)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Verisure platform."""
    locks = []
    if int(hub.config.get(CONF_LOCKS, 1)):
        hub.update_overview()
        locks.extend([
            VerisureDoorlock(device_label)
            for device_label in hub.get(
                "$.doorLockStatusList[*].deviceLabel")])

    add_devices(locks)


class VerisureDoorlock(LockDevice):
    """Representation of a Verisure doorlock."""

    def __init__(self, device_label):
        """Initialize the Verisure lock."""
        self._device_label = device_label
        self._state = STATE_UNKNOWN
        self._digits = hub.config.get(CONF_CODE_DIGITS)
        self._changed_by = None
        self._change_timestamp = 0

    @property
    def name(self):
        """Return the name of the lock."""
        return hub.get_first(
            "$.doorLockStatusList[?(@.deviceLabel=='%s')].area",
            self._device_label)

    @property
    def state(self):
        """Return the state of the lock."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return hub.get_first(
            "$.doorLockStatusList[?(@.deviceLabel=='%s')]",
            self._device_label) is not None

    @property
    def changed_by(self):
        """Last change triggered by."""
        return self._changed_by

    @property
    def code_format(self):
        """Return the required six digit code."""
        return '^\\d{%s}$' % self._digits

    def update(self):
        """Update lock status."""
        if time() - self._change_timestamp < 10:
            return
        hub.update_overview()
        status = hub.get_first(
            "$.doorLockStatusList[?(@.deviceLabel=='%s')].lockedState",
            self._device_label)
        if status == 'UNLOCKED':
            self._state = STATE_UNLOCKED
        elif status == 'LOCKED':
            self._state = STATE_LOCKED
        elif status != 'PENDING':
            _LOGGER.error('Unknown lock state %s', status)
        self._changed_by = hub.get_first(
            "$.doorLockStatusList[?(@.deviceLabel=='%s')].userString",
            self._device_label)

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state == STATE_LOCKED

    def unlock(self, **kwargs):
        """Send unlock command."""
        if self._state == STATE_UNLOCKED:
            return
        self.set_lock_state(kwargs[ATTR_CODE], STATE_UNLOCKED)

    def lock(self, **kwargs):
        """Send lock command."""
        if self._state == STATE_LOCKED:
            return
        self.set_lock_state(kwargs[ATTR_CODE], STATE_LOCKED)

    def set_lock_state(self, code, state):
        """Send set lock state command."""
        lock_state = 'lock' if state == STATE_LOCKED else 'unlock'
        transaction_id = hub.session.set_lock_state(
            code,
            self._device_label,
            lock_state)['doorLockStateChangeTransactionId']
        _LOGGER.debug("Verisure doorlock %s", state)
        transaction = {}
        while 'result' not in transaction:
            sleep(0.5)
            transaction = hub.session.get_lock_state_transaction(
                transaction_id)
        if transaction['result'] == 'OK':
            self._state = state
            self._change_timestamp = time()
