"""Intents for the media_player integration."""

from collections.abc import Iterable
from dataclasses import dataclass, field
import logging
import time
from typing import cast

import voluptuous as vol

from homeassistant.const import (
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_VOLUME_SET,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent

from . import (
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SEARCH_MEDIA,
    MediaPlayerDeviceClass,
    SearchMedia,
)
from .const import MediaPlayerEntityFeature, MediaPlayerState

INTENT_MEDIA_PAUSE = "HassMediaPause"
INTENT_MEDIA_UNPAUSE = "HassMediaUnpause"
INTENT_MEDIA_NEXT = "HassMediaNext"
INTENT_MEDIA_PREVIOUS = "HassMediaPrevious"
INTENT_SET_VOLUME = "HassSetVolume"
INTENT_MEDIA_SEARCH_AND_PLAY = "HassMediaSearchAndPlay"

_LOGGER = logging.getLogger(__name__)


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
                ATTR_MEDIA_VOLUME_LEVEL: intent.IntentSlotInfo(
                    description="The volume percentage of the media player",
                    value_schema=vol.All(
                        vol.Coerce(int),
                        vol.Range(min=0, max=100),
                        lambda val: val / 100,
                    ),
                ),
            },
            description="Sets the volume percentage of a media player",
            platforms={DOMAIN},
            device_classes={MediaPlayerDeviceClass},
        ),
    )
    intent.async_register(hass, MediaSearchAndPlayHandler())


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


class MediaSearchAndPlayHandler(intent.IntentHandler):
    """Handle HassMediaSearchAndPlay intents."""

    description = "Searches for media and plays the first result"

    intent_type = INTENT_MEDIA_SEARCH_AND_PLAY
    slot_schema = {
        vol.Required("search_query"): cv.string,
        # Optional name/area/floor slots handled by intent matcher
        vol.Optional("name"): cv.string,
        vol.Optional("area"): cv.string,
        vol.Optional("floor"): cv.string,
        vol.Optional("preferred_area_id"): cv.string,
        vol.Optional("preferred_floor_id"): cv.string,
    }
    platforms = {DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        search_query = slots["search_query"]["value"]

        # Entity name to match
        name_slot = slots.get("name", {})
        entity_name: str | None = name_slot.get("value")

        # Get area/floor info
        area_slot = slots.get("area", {})
        area_id = area_slot.get("value")

        floor_slot = slots.get("floor", {})
        floor_id = floor_slot.get("value")

        # Find matching entities
        match_constraints = intent.MatchTargetsConstraints(
            name=entity_name,
            area_name=area_id,
            floor_name=floor_id,
            domains={DOMAIN},
            assistant=intent_obj.assistant,
            features=MediaPlayerEntityFeature.SEARCH_MEDIA
            | MediaPlayerEntityFeature.PLAY_MEDIA,
            single_target=True,
        )
        match_result = intent.async_match_targets(
            hass,
            match_constraints,
            intent.MatchTargetsPreferences(
                area_id=slots.get("preferred_area_id", {}).get("value"),
                floor_id=slots.get("preferred_floor_id", {}).get("value"),
            ),
        )

        if not match_result.is_match:
            raise intent.MatchFailedError(
                result=match_result, constraints=match_constraints
            )

        target_entity = match_result.states[0]
        target_entity_id = target_entity.entity_id

        # 1. Search Media
        try:
            search_response = await hass.services.async_call(
                DOMAIN,
                SERVICE_SEARCH_MEDIA,
                {
                    "search_query": search_query,
                },
                target={
                    "entity_id": target_entity_id,
                },
                blocking=True,
                context=intent_obj.context,
                return_response=True,
            )
        except HomeAssistantError as err:
            _LOGGER.error("Error calling search_media: %s", err)
            raise intent.IntentHandleError(f"Error searching media: {err}") from err

        if (
            not search_response
            or not (
                entity_response := cast(
                    SearchMedia, search_response.get(target_entity_id)
                )
            )
            or not (results := entity_response.result)
        ):
            # No results found
            return intent_obj.create_response()

        # 2. Play Media (first result)
        first_result = results[0]
        try:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_PLAY_MEDIA,
                {
                    "entity_id": target_entity_id,
                    "media_content_id": first_result.media_content_id,
                    "media_content_type": first_result.media_content_type,
                },
                blocking=True,
                context=intent_obj.context,
            )
        except HomeAssistantError as err:
            _LOGGER.error("Error calling play_media: %s", err)
            raise intent.IntentHandleError(f"Error playing media: {err}") from err

        # Success
        response = intent_obj.create_response()
        response.async_set_speech_slots({"media": first_result})
        response.response_type = intent.IntentResponseType.ACTION_DONE
        return response
