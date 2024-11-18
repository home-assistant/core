"""Intents for the media_player integration."""

from collections.abc import Iterable
from dataclasses import dataclass, field
import time

import voluptuous as vol

from homeassistant.const import (
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_VOLUME_SET,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers import intent

from . import ATTR_MEDIA_VOLUME_LEVEL, DOMAIN, MediaPlayerDeviceClass
from .const import MediaPlayerEntityFeature, MediaPlayerState

INTENT_MEDIA_PAUSE = "HassMediaPause"
INTENT_MEDIA_UNPAUSE = "HassMediaUnpause"
INTENT_MEDIA_NEXT = "HassMediaNext"
INTENT_MEDIA_PREVIOUS = "HassMediaPrevious"
INTENT_SET_VOLUME = "HassSetVolume"


@dataclass
class LastPaused:
    """Information about last media players that were paused by voice."""

    timestamp: float | None = None
    context: Context | None = None
    entity_ids: set[str] = field(default_factory=set)

    def clear(self) -> None:
        """Clear timestamp and entities."""
        self.timestamp = None
        self.context = None
        self.entity_ids.clear()

    def update(self, context: Context | None, entity_ids: Iterable[str]) -> None:
        """Update last paused group."""
        self.context = context
        self.entity_ids = set(entity_ids)
        if self.entity_ids:
            self.timestamp = time.time()

    def __bool__(self) -> bool:
        """Return True if timestamp is set."""
        return self.timestamp is not None


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the media_player intents."""
    last_paused = LastPaused()

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
            description="Skips a media player to the next item",
            platforms={DOMAIN},
            device_classes={MediaPlayerDeviceClass},
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_MEDIA_PREVIOUS,
            DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            required_domains={DOMAIN},
            required_features=MediaPlayerEntityFeature.PREVIOUS_TRACK,
            required_states={MediaPlayerState.PLAYING},
            description="Replays the previous item for a media player",
            platforms={DOMAIN},
            device_classes={MediaPlayerDeviceClass},
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
            description="Sets the volume of a media player",
            platforms={DOMAIN},
            device_classes={MediaPlayerDeviceClass},
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
            description="Pauses a media player",
            platforms={DOMAIN},
            device_classes={MediaPlayerDeviceClass},
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
            self.last_paused.update(
                intent_obj.context, (s.entity_id for s in match_result.states)
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
            description="Resumes a media player",
            platforms={DOMAIN},
            device_classes={MediaPlayerDeviceClass},
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
        if match_result.is_match and (not match_constraints.name) and self.last_paused:
            assert self.last_paused.timestamp is not None

            # Check for a media player that was paused more recently than the
            # ones by voice.
            recent_state: State | None = None
            for state in match_result.states:
                if (state.last_changed_timestamp <= self.last_paused.timestamp) or (
                    state.context == self.last_paused.context
                ):
                    continue

                if (recent_state is None) or (
                    state.last_changed_timestamp > recent_state.last_changed_timestamp
                ):
                    recent_state = state

            if recent_state is not None:
                # Resume the more recently paused media player (outside of voice).
                match_result.states = [recent_state]
            else:
                # Resume only the previously paused media players if they are in the
                # targeted set.
                targeted_ids = {s.entity_id for s in match_result.states}
                overlapping_ids = targeted_ids.intersection(self.last_paused.entity_ids)
                if overlapping_ids:
                    match_result.states = [
                        s for s in match_result.states if s.entity_id in overlapping_ids
                    ]

            self.last_paused.clear()

        return await super().async_handle_states(
            intent_obj, match_result, match_constraints
        )
