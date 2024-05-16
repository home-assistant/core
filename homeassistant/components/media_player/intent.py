"""Intents for the media_player integration."""

from dataclasses import dataclass, field
import time
from typing import Final

import voluptuous as vol

from homeassistant.const import (
    EVENT_STATE_CHANGED,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_VOLUME_SET,
    STATE_PAUSED,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State
from homeassistant.helpers import intent

from . import ATTR_MEDIA_VOLUME_LEVEL, DOMAIN
from .const import MediaPlayerEntityFeature, MediaPlayerState

INTENT_MEDIA_PAUSE = "HassMediaPause"
INTENT_MEDIA_UNPAUSE = "HassMediaUnpause"
INTENT_MEDIA_NEXT = "HassMediaNext"
INTENT_SET_VOLUME = "HassSetVolume"

_PAUSE_DELAY: Final = 5


@dataclass
class LastPaused:
    """Information about last media players that were paused by voice."""

    timestamp: float | None = None
    entity_ids: set[str] = field(default_factory=set)
    waiting_entity_ids: set[str] = field(default_factory=set)


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the media_player intents."""
    last_paused = LastPaused()

    def state_changed_listener(event: Event[EventStateChangedData]) -> None:
        """Update last paused timestamp as expected media players enter their paused states."""
        if (
            ((state := event.data.get("new_state")) is None)
            or (state.domain != DOMAIN)
            or (state.state != STATE_PAUSED)
        ):
            return

        entity_id = state.entity_id
        if entity_id not in last_paused.waiting_entity_ids:
            return

        # Move out of waiting and bump timestamp
        last_paused.waiting_entity_ids.remove(entity_id)
        last_paused.entity_ids.add(entity_id)
        last_paused.timestamp = time.time()

    hass.bus.async_listen(EVENT_STATE_CHANGED, state_changed_listener)

    intent.async_register(hass, MediaUnpauseHandler(last_paused))
    intent.async_register(hass, MediaPauseHandler(last_paused))
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_MEDIA_NEXT,
            DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            required_domains={DOMAIN},
            required_features=MediaPlayerEntityFeature.NEXT_TRACK,
            required_states={MediaPlayerState.PLAYING},
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_SET_VOLUME,
            DOMAIN,
            SERVICE_VOLUME_SET,
            required_domains={DOMAIN},
            required_states={MediaPlayerState.PLAYING},
            required_features=MediaPlayerEntityFeature.VOLUME_SET,
            required_slots={
                ATTR_MEDIA_VOLUME_LEVEL: vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100), lambda val: val / 100
                )
            },
        ),
    )


class MediaPauseHandler(intent.ServiceIntentHandler):
    """Handler for pause intent. Records last paused media players."""

    def __init__(self, last_paused: LastPaused) -> None:
        """Initialize handler."""
        super().__init__(
            INTENT_MEDIA_PAUSE,
            DOMAIN,
            SERVICE_MEDIA_PAUSE,
            required_domains={DOMAIN},
            required_features=MediaPlayerEntityFeature.PAUSE,
            required_states={MediaPlayerState.PLAYING},
        )
        self.last_paused = last_paused

    async def async_handle_states(
        self,
        intent_obj: intent.Intent,
        match_result: intent.MatchTargetsResult,
        match_constraints: intent.MatchTargetsConstraints,
        match_preferences: intent.MatchTargetsPreferences | None = None,
    ) -> intent.IntentResponse:
        """Record last paused media players."""
        if match_result.is_match:
            # Save entity ids of paused media players
            self.last_paused.timestamp = time.time()
            self.last_paused.entity_ids.clear()
            self.last_paused.waiting_entity_ids.clear()
            self.last_paused.waiting_entity_ids.update(
                s.entity_id for s in match_result.states
            )

        return await super().async_handle_states(
            intent_obj, match_result, match_constraints
        )


class MediaUnpauseHandler(intent.ServiceIntentHandler):
    """Handler for unpause/resume intent. Uses last paused media players."""

    def __init__(self, last_paused: LastPaused) -> None:
        """Initialize handler."""
        super().__init__(
            INTENT_MEDIA_UNPAUSE,
            DOMAIN,
            SERVICE_MEDIA_PLAY,
            required_domains={DOMAIN},
            required_states={MediaPlayerState.PAUSED},
        )
        self.last_paused = last_paused

    async def async_handle_states(
        self,
        intent_obj: intent.Intent,
        match_result: intent.MatchTargetsResult,
        match_constraints: intent.MatchTargetsConstraints,
        match_preferences: intent.MatchTargetsPreferences | None = None,
    ) -> intent.IntentResponse:
        """Unpause last paused media players."""
        if (
            match_result.is_match
            and (not match_constraints.name)
            and (self.last_paused.timestamp is not None)
            and self.last_paused.entity_ids
        ):
            # Check for a media player that was paused more recently than the
            # ones by voice.
            recent_state: State | None = None
            for state in match_result.states:
                if state.last_changed_timestamp <= self.last_paused.timestamp:
                    continue

                if (recent_state is None) or (
                    state.last_changed_timestamp > recent_state.last_changed_timestamp
                ):
                    recent_state = state

            if recent_state is not None:
                # Resume the more recently paused media player (outside of voice).
                match_result.states = [recent_state]
                self.last_paused.timestamp = None
                self.last_paused.entity_ids.clear()
                self.last_paused.waiting_entity_ids.clear()
            else:
                # Resume only the previously paused media players if they are in the
                # targeted set.
                targeted_ids = {s.entity_id for s in match_result.states}
                overlapping_ids = targeted_ids.intersection(self.last_paused.entity_ids)
                if overlapping_ids:
                    match_result.states = [
                        s for s in match_result.states if s.entity_id in overlapping_ids
                    ]

        return await super().async_handle_states(
            intent_obj, match_result, match_constraints
        )
