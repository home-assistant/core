"""Class to hold all lock accessories."""

import logging
from typing import Any

from pyhap.const import CATEGORY_DOOR_LOCK

from homeassistant.components.lock import (
    DOMAIN,
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.const import ATTR_CODE, ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import State, callback

from .accessories import TYPES, HomeAccessory
from .const import CHAR_LOCK_CURRENT_STATE, CHAR_LOCK_TARGET_STATE, SERV_LOCK

_LOGGER = logging.getLogger(__name__)

HASS_TO_HOMEKIT_CURRENT = {
    STATE_UNLOCKED: 0,
    STATE_UNLOCKING: 1,
    STATE_LOCKING: 0,
    STATE_LOCKED: 1,
    STATE_JAMMED: 2,
    STATE_UNKNOWN: 3,
}

HASS_TO_HOMEKIT_TARGET = {
    STATE_UNLOCKED: 0,
    STATE_UNLOCKING: 0,
    STATE_LOCKING: 1,
    STATE_LOCKED: 1,
}

VALID_TARGET_STATES = {STATE_LOCKING, STATE_UNLOCKING, STATE_LOCKED, STATE_UNLOCKED}

HOMEKIT_TO_HASS = {
    0: STATE_UNLOCKED,
    1: STATE_LOCKED,
    2: STATE_JAMMED,
    3: STATE_UNKNOWN,
}

STATE_TO_SERVICE = {
    STATE_LOCKING: "unlock",
    STATE_LOCKED: "lock",
    STATE_UNLOCKING: "lock",
    STATE_UNLOCKED: "unlock",
}


@TYPES.register("Lock")
class Lock(HomeAccessory):
    """Generate a Lock accessory for a lock entity.

    The lock entity must support: unlock and lock.
    """

    def __init__(self, *args: Any) -> None:
        """Initialize a Lock accessory object."""
        super().__init__(*args, category=CATEGORY_DOOR_LOCK)
        self._code = self.config.get(ATTR_CODE)
        state = self.hass.states.get(self.entity_id)
        assert state is not None

        serv_lock_mechanism = self.add_preload_service(SERV_LOCK)
        self.char_current_state = serv_lock_mechanism.configure_char(
            CHAR_LOCK_CURRENT_STATE, value=HASS_TO_HOMEKIT_CURRENT[STATE_UNKNOWN]
        )
        self.char_target_state = serv_lock_mechanism.configure_char(
            CHAR_LOCK_TARGET_STATE,
            value=HASS_TO_HOMEKIT_CURRENT[STATE_LOCKED],
            setter_callback=self.set_state,
        )
        self.async_update_state(state)

    def set_state(self, value: int) -> None:
        """Set lock state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set state to %d", self.entity_id, value)

        hass_value = HOMEKIT_TO_HASS[value]
        service = STATE_TO_SERVICE[hass_value]

        params = {ATTR_ENTITY_ID: self.entity_id}
        if self._code:
            params[ATTR_CODE] = self._code
        self.async_call_service(DOMAIN, service, params)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update lock after state changed."""
        hass_state = new_state.state
        current_lock_state = HASS_TO_HOMEKIT_CURRENT.get(
            hass_state, HASS_TO_HOMEKIT_CURRENT[STATE_UNKNOWN]
        )
        target_lock_state = HASS_TO_HOMEKIT_TARGET.get(hass_state)
        _LOGGER.debug(
            "%s: Updated current state to %s (current=%d) (target=%s)",
            self.entity_id,
            hass_state,
            current_lock_state,
            target_lock_state,
        )
        # LockTargetState only supports locked and unlocked
        # Must set lock target state before current state
        # or there will be no notification
        if target_lock_state is not None:
            self.char_target_state.set_value(target_lock_state)

        # Set lock current state ONLY after ensuring that
        # target state is correct or there will be no
        # notification
        self.char_current_state.set_value(current_lock_state)
