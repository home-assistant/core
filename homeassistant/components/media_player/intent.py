"""Intents for the media_player integration."""

import voluptuous as vol

from homeassistant.const import (
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_VOLUME_SET,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import ATTR_MEDIA_VOLUME_LEVEL, DOMAIN
from .const import MediaPlayerEntityFeature, MediaPlayerState

INTENT_MEDIA_PAUSE = "HassMediaPause"
INTENT_MEDIA_UNPAUSE = "HassMediaUnpause"
INTENT_MEDIA_NEXT = "HassMediaNext"
INTENT_SET_VOLUME = "HassSetVolume"

DATA_LAST_PAUSED = f"{DOMAIN}.last_paused"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the media_player intents."""
    intent.async_register(hass, MediaUnpauseHandler())
    intent.async_register(hass, MediaPauseHandler())
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

    def __init__(self) -> None:
        """Initialize handler."""
        super().__init__(
            INTENT_MEDIA_PAUSE,
            DOMAIN,
            SERVICE_MEDIA_PAUSE,
            required_domains={DOMAIN},
            required_features=MediaPlayerEntityFeature.PAUSE,
            required_states={MediaPlayerState.PLAYING},
        )

    async def async_handle_states(
        self,
        intent_obj: intent.Intent,
        match_result: intent.MatchTargetsResult,
        match_constraints: intent.MatchTargetsConstraints,
        match_preferences: intent.MatchTargetsPreferences | None = None,
    ) -> intent.IntentResponse:
        """Record last paused media players."""
        hass = intent_obj.hass

        if match_result.is_match:
            # Save entity ids of paused media players
            hass.data[DATA_LAST_PAUSED] = {s.entity_id for s in match_result.states}

        return await super().async_handle_states(
            intent_obj, match_result, match_constraints
        )


class MediaUnpauseHandler(intent.ServiceIntentHandler):
    """Handler for unpause/resume intent. Uses last paused media players."""

    def __init__(self) -> None:
        """Initialize handler."""
        super().__init__(
            INTENT_MEDIA_UNPAUSE,
            DOMAIN,
            SERVICE_MEDIA_PLAY,
            required_domains={DOMAIN},
            required_states={MediaPlayerState.PAUSED},
        )

    async def async_handle_states(
        self,
        intent_obj: intent.Intent,
        match_result: intent.MatchTargetsResult,
        match_constraints: intent.MatchTargetsConstraints,
        match_preferences: intent.MatchTargetsPreferences | None = None,
    ) -> intent.IntentResponse:
        """Unpause last paused media players."""
        hass = intent_obj.hass

        if (
            match_result.is_match
            and (not match_constraints.name)
            and (last_paused := hass.data.get(DATA_LAST_PAUSED))
        ):
            # Resume only the previously paused media players if they are in the
            # targeted set.
            targeted_ids = {s.entity_id for s in match_result.states}
            overlapping_ids = targeted_ids.intersection(last_paused)
            if overlapping_ids:
                match_result.states = [
                    s for s in match_result.states if s.entity_id in overlapping_ids
                ]

        return await super().async_handle_states(
            intent_obj, match_result, match_constraints
        )
