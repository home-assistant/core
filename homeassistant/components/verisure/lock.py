"""Support for Verisure locks."""
from time import monotonic, sleep

from homeassistant.components.lock import LockEntity
from homeassistant.const import ATTR_CODE, STATE_LOCKED, STATE_UNLOCKED

from . import HUB as hub
from .const import CONF_CODE_DIGITS, CONF_DEFAULT_LOCK_CODE, CONF_LOCKS, LOGGER


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Verisure lock platform."""
    locks = []
    if int(hub.config.get(CONF_LOCKS, 1)):
        hub.update_overview()
        locks.extend(
            [
                VerisureDoorlock(device_label)
                for device_label in hub.get("$.doorLockStatusList[*].deviceLabel")
            ]
        )

    add_entities(locks)


class VerisureDoorlock(LockEntity):
    """Representation of a Verisure doorlock."""

    def __init__(self, device_label):
        """Initialize the Verisure lock."""
        self._device_label = device_label
        self._state = None
        self._digits = hub.config.get(CONF_CODE_DIGITS)
        self._changed_by = None
        self._change_timestamp = 0
        self._default_lock_code = hub.config.get(CONF_DEFAULT_LOCK_CODE)

    @property
    def name(self):
        """Return the name of the lock."""
        return hub.get_first(
            "$.doorLockStatusList[?(@.deviceLabel=='%s')].area", self._device_label
        )

    @property
    def state(self):
        """Return the state of the lock."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return (
            hub.get_first(
                "$.doorLockStatusList[?(@.deviceLabel=='%s')]", self._device_label
            )
            is not None
        )

    @property
    def changed_by(self):
        """Last change triggered by."""
        return self._changed_by

    @property
    def code_format(self):
        """Return the required six digit code."""
        return "^\\d{%s}$" % self._digits

    def update(self):
        """Update lock status."""
        if monotonic() - self._change_timestamp < 10:
            return
        hub.update_overview()
        status = hub.get_first(
            "$.doorLockStatusList[?(@.deviceLabel=='%s')].lockedState",
            self._device_label,
        )
        if status == "UNLOCKED":
            self._state = STATE_UNLOCKED
        elif status == "LOCKED":
            self._state = STATE_LOCKED
        elif status != "PENDING":
            LOGGER.error("Unknown lock state %s", status)
        self._changed_by = hub.get_first(
            "$.doorLockStatusList[?(@.deviceLabel=='%s')].userString",
            self._device_label,
        )

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state == STATE_LOCKED

    def unlock(self, **kwargs):
        """Send unlock command."""
        if self._state is None:
            return

        code = kwargs.get(ATTR_CODE, self._default_lock_code)
        if code is None:
            LOGGER.error("Code required but none provided")
            return

        self.set_lock_state(code, STATE_UNLOCKED)

    def lock(self, **kwargs):
        """Send lock command."""
        if self._state == STATE_LOCKED:
            return

        code = kwargs.get(ATTR_CODE, self._default_lock_code)
        if code is None:
            LOGGER.error("Code required but none provided")
            return

        self.set_lock_state(code, STATE_LOCKED)

    def set_lock_state(self, code, state):
        """Send set lock state command."""
        lock_state = "lock" if state == STATE_LOCKED else "unlock"
        transaction_id = hub.session.set_lock_state(
            code, self._device_label, lock_state
        )["doorLockStateChangeTransactionId"]
        LOGGER.debug("Verisure doorlock %s", state)
        transaction = {}
        attempts = 0
        while "result" not in transaction:
            transaction = hub.session.get_lock_state_transaction(transaction_id)
            attempts += 1
            if attempts == 30:
                break
            if attempts > 1:
                sleep(0.5)
        if transaction["result"] == "OK":
            self._state = state
            self._change_timestamp = monotonic()
