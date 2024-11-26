"""Class to hold all lock accessories."""

import logging
from typing import Any

from pyhap.const import CATEGORY_DOOR_LOCK

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.const import ATTR_CODE, ATTR_ENTITY_ID, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State, callback

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_LOCK_CURRENT_STATE, 
    CHAR_LOCK_TARGET_STATE,
    CHAR_MUTE,
    CHAR_PROGRAMMABLE_SWITCH_EVENT,
    CONF_LINKED_DOORBELL_SENSOR, 
    SERV_DOORBELL,
    SERV_LOCK,
    SERV_SPEAKER, 
    SERV_STATELESS_PROGRAMMABLE_SWITCH
)

_LOGGER = logging.getLogger(__name__)

DOORBELL_SINGLE_PRESS = 0
DOORBELL_DOUBLE_PRESS = 1
DOORBELL_LONG_PRESS = 2

HASS_TO_HOMEKIT_CURRENT = {
    LockState.UNLOCKED.value: 0,
    LockState.UNLOCKING.value: 1,
    LockState.LOCKING.value: 0,
    LockState.LOCKED.value: 1,
    LockState.JAMMED.value: 2,
    STATE_UNKNOWN: 3,
}

HASS_TO_HOMEKIT_TARGET = {
    LockState.UNLOCKED.value: 0,
    LockState.UNLOCKING.value: 0,
    LockState.LOCKING.value: 1,
    LockState.LOCKED.value: 1,
}

VALID_TARGET_STATES = {
    LockState.LOCKING.value,
    LockState.UNLOCKING.value,
    LockState.LOCKED.value,
    LockState.UNLOCKED.value,
}

HOMEKIT_TO_HASS = {
    0: LockState.UNLOCKED.value,
    1: LockState.LOCKED.value,
    2: LockState.JAMMED.value,
    3: STATE_UNKNOWN,
}

STATE_TO_SERVICE = {
    LockState.LOCKING.value: "unlock",
    LockState.LOCKED.value: "lock",
    LockState.UNLOCKING.value: "lock",
    LockState.UNLOCKED.value: "unlock",
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
            value=HASS_TO_HOMEKIT_CURRENT[LockState.LOCKED.value],
            setter_callback=self.set_state,
        )
        
        self.async_update_state(state)
        self.init_doorbell(self)


    def init_doorbell(self) -> None:
        self.char_doorbell_detected = None
        self.char_doorbell_detected_switch = None
        linked_doorbell_sensor: str | None = self.config.get(
            CONF_LINKED_DOORBELL_SENSOR
        )
        self.linked_doorbell_sensor = linked_doorbell_sensor
        self.doorbell_is_event = False
        if not linked_doorbell_sensor:
            return
        self.doorbell_is_event = linked_doorbell_sensor.startswith("event.")
        if not (state := self.hass.states.get(linked_doorbell_sensor)):
            return
        serv_doorbell = self.add_preload_service(SERV_DOORBELL)
        self.set_primary_service(serv_doorbell)
        self.char_doorbell_detected = serv_doorbell.configure_char(
            CHAR_PROGRAMMABLE_SWITCH_EVENT,
            value=0,
        )
        serv_stateless_switch = self.add_preload_service(
            SERV_STATELESS_PROGRAMMABLE_SWITCH
        )
        self.char_doorbell_detected_switch = serv_stateless_switch.configure_char(
            CHAR_PROGRAMMABLE_SWITCH_EVENT,
            value=0,
            valid_values={"SinglePress": DOORBELL_SINGLE_PRESS},
        )
        serv_speaker = self.add_preload_service(SERV_SPEAKER)
        serv_speaker.configure_char(CHAR_MUTE, value=0)
        self.async_update_doorbell_state(None, state)

    @pyhap_callback  # type: ignore[misc]
    @callback
    def run(self) -> None:
        """Handle accessory driver started event.

        Run inside the Home Assistant event loop.
        """
        if self.char_doorbell_detected:
            assert self.linked_doorbell_sensor
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    self.linked_doorbell_sensor,
                    self.async_update_doorbell_state_event,
                    job_type=HassJobType.Callback,
                )
            )

        super().run()

    def set_state(self, value: int) -> None:
        """Set lock state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set state to %d", self.entity_id, value)

        hass_value = HOMEKIT_TO_HASS[value]
        service = STATE_TO_SERVICE[hass_value]

        params = {ATTR_ENTITY_ID: self.entity_id}
        if self._code:
            params[ATTR_CODE] = self._code
        self.async_call_service(LOCK_DOMAIN, service, params)

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

    @callback
    def async_update_doorbell_state_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state change event listener callback."""
        if not state_changed_event_is_same_state(event) and (
            new_state := event.data["new_state"]
        ):
            self.async_update_doorbell_state(event.data["old_state"], new_state)

    @callback
    def async_update_doorbell_state(
        self, old_state: State | None, new_state: State
    ) -> None:
        """Handle link doorbell sensor state change to update HomeKit value."""
        assert self.char_doorbell_detected
        assert self.char_doorbell_detected_switch
        state = new_state.state
        if state == STATE_ON or (
            self.doorbell_is_event
            and old_state is not None
            and old_state.state != STATE_UNAVAILABLE
            and state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            self.char_doorbell_detected.set_value(DOORBELL_SINGLE_PRESS)
            self.char_doorbell_detected_switch.set_value(DOORBELL_SINGLE_PRESS)
            _LOGGER.debug(
                "%s: Set linked doorbell %s sensor to %d",
                self.entity_id,
                self.linked_doorbell_sensor,
                DOORBELL_SINGLE_PRESS,
            )
