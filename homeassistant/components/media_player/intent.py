"""Intents for the media_player integration."""

import asyncio
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
    SERVICE_VOLUME_MUTE,
    STATE_PLAYING,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.entity_component import EntityComponent

from . import MediaPlayerDeviceClass, MediaPlayerEntity
from .browse_media import SearchMedia
from .const import (
    ATTR_MEDIA_FILTER_CLASSES,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SEARCH_MEDIA,
    MediaClass,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)

MULTIPLE_PLAYERS_MATCHED_RESPONSE = "multiple_players_matched"

INTENT_MEDIA_PAUSE = "HassMediaPause"
INTENT_MEDIA_UNPAUSE = "HassMediaUnpause"
INTENT_MEDIA_NEXT = "HassMediaNext"
INTENT_MEDIA_PREVIOUS = "HassMediaPrevious"
INTENT_PLAYER_MUTE = "HassMediaPlayerMute"
INTENT_PLAYER_UNMUTE = "HassMediaPlayerUnmute"
INTENT_SET_VOLUME = "HassSetVolume"
INTENT_SET_VOLUME_RELATIVE = "HassSetVolumeRelative"
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
    intent.async_register(hass, MediaSetVolumeHandler())
    intent.async_register(hass, MediaSetVolumeRelativeHandler())
    intent.async_register(hass, MediaPlayerMuteUnmuteHandler(True))
    intent.async_register(hass, MediaPlayerMuteUnmuteHandler(False))
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


class MediaPlayerMuteUnmuteHandler(intent.ServiceIntentHandler):
    """Handle Mute/Unmute intents."""

    def __init__(self, is_volume_muted: bool) -> None:
        """Initialize the mute/unmute handler objects."""

        super().__init__(
            (INTENT_PLAYER_MUTE if is_volume_muted else INTENT_PLAYER_UNMUTE),
            DOMAIN,
            SERVICE_VOLUME_MUTE,
            required_domains={DOMAIN},
            required_features=MediaPlayerEntityFeature.VOLUME_MUTE,
            optional_slots={
                ATTR_MEDIA_VOLUME_MUTED: intent.IntentSlotInfo(
                    description="Whether the media player should be muted or unmuted",
                    value_schema=vol.Boolean(),
                ),
            },
            description=(
                "Mutes a media player" if is_volume_muted else "Unmutes a media player"
            ),
            platforms={DOMAIN},
            device_classes={MediaPlayerDeviceClass},
        )
        self.is_volume_muted = is_volume_muted

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""

        intent_obj.slots["is_volume_muted"] = {
            "value": self.is_volume_muted,
            "text": str(self.is_volume_muted),
        }
        return await super().async_handle(intent_obj)


class MediaSearchAndPlayHandler(intent.IntentHandler):
    """Handle HassMediaSearchAndPlay intents."""

    description = "Searches for media and plays the first result"

    intent_type = INTENT_MEDIA_SEARCH_AND_PLAY
    slot_schema = {
        vol.Required("search_query"): cv.string,
        vol.Optional("media_class"): vol.In([cls.value for cls in MediaClass]),
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

        # Get media class if provided
        media_class_slot = slots.get("media_class", {})
        media_class_value = media_class_slot.get("value")

        # Build search service data
        search_data = {"search_query": search_query}

        # Add media_filter_classes if media_class is provided
        if media_class_value:
            search_data[ATTR_MEDIA_FILTER_CLASSES] = [media_class_value]

        # 1. Search Media
        try:
            search_response = await hass.services.async_call(
                DOMAIN,
                SERVICE_SEARCH_MEDIA,
                search_data,
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
        response.async_set_speech_slots({"media": first_result.as_dict()})
        return response


class MediaSetVolumeHandler(intent.IntentHandler):
    """Handler for setting volume."""

    description = "Set the volume of a media player"
    intent_type = INTENT_SET_VOLUME
    slot_schema = {
        vol.Required("volume_level"): vol.All(
            vol.Coerce(int),
            vol.Range(min=0, max=100),
            lambda val: val / 100,
        ),
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
        component: EntityComponent[MediaPlayerEntity] = hass.data[DOMAIN]

        slots = self.async_validate_slots(intent_obj.slots)

        volume_level = slots["volume_level"]["value"]

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
            features=MediaPlayerEntityFeature.VOLUME_SET,
        )
        match_preferences = intent.MatchTargetsPreferences(
            area_id=slots.get("preferred_area_id", {}).get("value"),
            floor_id=slots.get("preferred_floor_id", {}).get("value"),
        )
        match_result = intent.async_match_targets(
            hass, match_constraints, match_preferences
        )

        if not match_result.is_match:
            # No targets
            raise intent.MatchFailedError(
                result=match_result, constraints=match_constraints
            )

        if (
            match_result.is_match
            and (len(match_result.states) > 1)
            and ("name" not in intent_obj.slots)
        ):
            # Multiple targets not by name, so we need to check state
            match_result.states = [
                s for s in match_result.states if s.state == STATE_PLAYING
            ]
            if not match_result.states:
                # No media players are playing
                raise intent.MatchFailedError(
                    result=intent.MatchTargetsResult(
                        is_match=False, no_match_reason=intent.MatchFailedReason.STATE
                    ),
                    constraints=match_constraints,
                    preferences=match_preferences,
                )

        target_entity_ids = {s.entity_id for s in match_result.states}
        target_entities = [
            e for e in component.entities if e.entity_id in target_entity_ids
        ]

        coros = [e.async_set_volume_level(volume_level) for e in target_entities]

        try:
            await asyncio.gather(*coros)
        except HomeAssistantError as err:
            _LOGGER.error("Error setting volume: %s", err)
            raise intent.IntentHandleError(f"Error setting volume: {err}") from err

        response = intent_obj.create_response()
        response.async_set_states(match_result.states)
        return response


class MediaSetVolumeRelativeHandler(intent.IntentHandler):
    """Handler for setting relative volume."""

    description = "Increases or decreases the volume of a media player"

    intent_type = INTENT_SET_VOLUME_RELATIVE
    slot_schema = {
        vol.Required("volume_step"): vol.Any(
            "up",
            "down",
            vol.All(
                vol.Coerce(int),
                vol.Range(min=-100, max=100),
                lambda val: val / 100,
            ),
        ),
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
        component: EntityComponent[MediaPlayerEntity] = hass.data[DOMAIN]

        slots = self.async_validate_slots(intent_obj.slots)
        volume_step = slots["volume_step"]["value"]

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
            features=MediaPlayerEntityFeature.VOLUME_SET,
        )
        match_preferences = intent.MatchTargetsPreferences(
            area_id=slots.get("preferred_area_id", {}).get("value"),
            floor_id=slots.get("preferred_floor_id", {}).get("value"),
        )
        match_result = intent.async_match_targets(
            hass, match_constraints, match_preferences
        )

        if not match_result.is_match:
            # No targets
            raise intent.MatchFailedError(
                result=match_result, constraints=match_constraints
            )

        if (
            match_result.is_match
            and (len(match_result.states) > 1)
            and ("name" not in intent_obj.slots)
        ):
            # Multiple targets not by name, so we need to check state
            match_result.states = [
                s for s in match_result.states if s.state == STATE_PLAYING
            ]
            if not match_result.states:
                # No media players are playing
                raise intent.MatchFailedError(
                    result=intent.MatchTargetsResult(
                        is_match=False, no_match_reason=intent.MatchFailedReason.STATE
                    ),
                    constraints=match_constraints,
                    preferences=match_preferences,
                )

        target_entity_ids = {s.entity_id for s in match_result.states}
        target_entities = [
            e for e in component.entities if e.entity_id in target_entity_ids
        ]

        if volume_step == "up":
            coros = [e.async_volume_up() for e in target_entities]
        elif volume_step == "down":
            coros = [e.async_volume_down() for e in target_entities]
        else:
            coros = [
                e.async_set_volume_level(
                    max(0.0, min(1.0, e.volume_level + volume_step))
                )
                for e in target_entities
            ]

        try:
            await asyncio.gather(*coros)
        except HomeAssistantError as err:
            _LOGGER.error("Error setting relative volume: %s", err)
            raise intent.IntentHandleError(
                f"Error setting relative volume: {err}"
            ) from err

        response = intent_obj.create_response()
        response.async_set_states(match_result.states)
        return response
