"""Mixin base doorball class for homekit accessories."""

import logging
from typing import Any

from pyhap.util import callback as pyhap_callback

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HassJobType,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.event import async_track_state_change_event

from .accessories import HomeAccessory, HomeDriver
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
    """Base class including doorball event."""

    def __init__(
        self,
        hass: HomeAssistant,
        driver: HomeDriver,
        name: str,
        entity_id: str,
        aid: int,
        config: dict[str, Any],
        *args: Any,
        category: int,
        **kwargs: Any,
    ) -> None:
        """Initialize doorbell mixin accessory object."""
        super().__init__(
            hass,
            driver,
            name,
            entity_id,
            aid,
            config,
            category,
            *args,  # noqa: B026
            **kwargs,
        )

        self._char_doorbell_detected = None
        self._char_doorbell_detected_switch = None
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
        self._async_update_doorbell_state(None, state)

    @pyhap_callback  # type: ignore[misc]
    @callback
    def run(self) -> None:
        """Handle accessory driver started event.

        Run inside the Home Assistant event loop.
        """
        if self._char_doorbell_detected:
            assert self.linked_doorbell_sensor
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    self.linked_doorbell_sensor,
                    self._async_update_doorbell_state_event,
                    job_type=HassJobType.Callback,
                )
            )

        super().run()

    @callback
    def _async_update_doorbell_state_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state change event listener callback."""
        if not state_changed_event_is_same_state(event) and (
            new_state := event.data["new_state"]
        ):
            self._async_update_doorbell_state(event.data["old_state"], new_state)

    @callback
    def _async_update_doorbell_state(
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
