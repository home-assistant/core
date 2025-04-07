"""Extend the doorbell functions."""

from __future__ import annotations

import logging
from typing import Any

from pyhap.util import callback as pyhap_callback

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HassJobType,
    State,
    callback as ha_callback,
)
from homeassistant.helpers.event import async_track_state_change_event

from .accessories import HomeAccessory
from .const import (
    CHAR_MUTE,
    CHAR_PROGRAMMABLE_SWITCH_EVENT,
    CONF_LINKED_DOORBELL_SENSOR,
    SERV_DOORBELL,
    SERV_SPEAKER,
    SERV_STATELESS_PROGRAMMABLE_SWITCH,
)
from .util import state_changed_event_is_same_state

_LOGGER = logging.getLogger(__name__)

DOORBELL_SINGLE_PRESS = 0
DOORBELL_DOUBLE_PRESS = 1
DOORBELL_LONG_PRESS = 2


class HomeDoorbellAccessory(HomeAccessory):
    """Accessory with optional doorbell."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize an Accessory object with optional attached doorbell."""
        super().__init__(*args, **kwargs)
        self._char_doorbell_detected = None
        self._char_doorbell_detected_switch = None
        linked_doorbell_sensor: str | None
        linked_doorbell_sensor = self.config.get(CONF_LINKED_DOORBELL_SENSOR)
        self.linked_doorbell_sensor = linked_doorbell_sensor
        self.doorbell_is_event = False
        if not linked_doorbell_sensor:
            return
        self.doorbell_is_event = linked_doorbell_sensor.startswith("event.")
        if not (state := self.hass.states.get(linked_doorbell_sensor)):
            return
        serv_doorbell = self.add_preload_service(SERV_DOORBELL)
        self.set_primary_service(serv_doorbell)
        self._char_doorbell_detected = serv_doorbell.configure_char(
            CHAR_PROGRAMMABLE_SWITCH_EVENT,
            value=0,
        )
        serv_stateless_switch = self.add_preload_service(
            SERV_STATELESS_PROGRAMMABLE_SWITCH
        )
        self._char_doorbell_detected_switch = serv_stateless_switch.configure_char(
            CHAR_PROGRAMMABLE_SWITCH_EVENT,
            value=0,
            valid_values={"SinglePress": DOORBELL_SINGLE_PRESS},
        )
        serv_speaker = self.add_preload_service(SERV_SPEAKER)
        serv_speaker.configure_char(CHAR_MUTE, value=0)
        self.async_update_doorbell_state(None, state)

    @ha_callback
    @pyhap_callback  # type: ignore[misc]
    def run(self) -> None:
        """Handle doorbell event."""
        if self._char_doorbell_detected:
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

    @ha_callback
    def async_update_doorbell_state_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state change event listener callback."""
        if not state_changed_event_is_same_state(event) and (
            new_state := event.data["new_state"]
        ):
            self.async_update_doorbell_state(event.data["old_state"], new_state)

    @ha_callback
    def async_update_doorbell_state(
        self, old_state: State | None, new_state: State
    ) -> None:
        """Handle link doorbell sensor state change to update HomeKit value."""
        assert self._char_doorbell_detected
        assert self._char_doorbell_detected_switch
        state = new_state.state
        if state == STATE_ON or (
            self.doorbell_is_event
            and old_state is not None
            and old_state.state != STATE_UNAVAILABLE
            and state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            self._char_doorbell_detected.set_value(DOORBELL_SINGLE_PRESS)
            self._char_doorbell_detected_switch.set_value(DOORBELL_SINGLE_PRESS)
            _LOGGER.debug(
                "%s: Set linked doorbell %s sensor to %d",
                self.entity_id,
                self.linked_doorbell_sensor,
                DOORBELL_SINGLE_PRESS,
            )
