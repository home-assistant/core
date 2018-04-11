"""Class to hold all lock accessories."""
import logging

from homeassistant.components.lock import (
    ATTR_ENTITY_ID, STATE_LOCKED, STATE_UNLOCKED, STATE_UNKNOWN)

from . import TYPES
from .accessories import HomeAccessory, add_preload_service, setup_char
from .const import (
    CATEGORY_LOCK, SERV_LOCK, CHAR_LOCK_CURRENT_STATE, CHAR_LOCK_TARGET_STATE)

_LOGGER = logging.getLogger(__name__)

HASS_TO_HOMEKIT = {STATE_UNLOCKED: 0,
                   STATE_LOCKED: 1,
                   # value 2 is Jammed which hass doesn't have a state for
                   STATE_UNKNOWN: 3}
HOMEKIT_TO_HASS = {c: s for s, c in HASS_TO_HOMEKIT.items()}
STATE_TO_SERVICE = {STATE_LOCKED: 'lock',
                    STATE_UNLOCKED: 'unlock'}


@TYPES.register('Lock')
class Lock(HomeAccessory):
    """Generate a Lock accessory for a lock entity.

    The lock entity must support: unlock and lock.
    """

    def __init__(self, *args, config):
        """Initialize a Lock accessory object."""
        super().__init__(*args, category=CATEGORY_LOCK)
        self.flag_target_state = False

        serv_lock_mechanism = add_preload_service(self, SERV_LOCK)
        self.char_current_state = setup_char(
            CHAR_LOCK_CURRENT_STATE, serv_lock_mechanism,
            value=HASS_TO_HOMEKIT[STATE_UNKNOWN])
        self.char_target_state = setup_char(
            CHAR_LOCK_TARGET_STATE, serv_lock_mechanism,
            value=HASS_TO_HOMEKIT[STATE_LOCKED], callback=self.set_state)

    def set_state(self, value):
        """Set lock state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set state to %d", self.entity_id, value)
        self.flag_target_state = True

        hass_value = HOMEKIT_TO_HASS.get(value)
        service = STATE_TO_SERVICE[hass_value]

        params = {ATTR_ENTITY_ID: self.entity_id}
        self.hass.services.call('lock', service, params)

    def update_state(self, new_state):
        """Update lock after state changed."""
        hass_state = new_state.state
        if hass_state in HASS_TO_HOMEKIT:
            current_lock_state = HASS_TO_HOMEKIT[hass_state]
            self.char_current_state.set_value(current_lock_state)
            _LOGGER.debug('%s: Updated current state to %s (%d)',
                          self.entity_id, hass_state, current_lock_state)

            # LockTargetState only supports locked and unlocked
            if hass_state in (STATE_LOCKED, STATE_UNLOCKED):
                if not self.flag_target_state:
                    self.char_target_state.set_value(current_lock_state)
                self.flag_target_state = False
