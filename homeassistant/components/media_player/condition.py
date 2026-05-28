"""Provides conditions for media players."""

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    Condition,
    EntityConditionBase,
    EntityNumericalConditionBase,
    make_entity_state_condition,
)

from . import ATTR_MEDIA_VOLUME_LEVEL, ATTR_MEDIA_VOLUME_MUTED
from .const import DOMAIN, MediaPlayerState


class _MediaPlayerMutedConditionBase(EntityConditionBase):
    """Base class for media player is_muted/is_unmuted conditions."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _target_muted: bool

    def _state_valid_since(self, state: State) -> datetime:
        """Anchor `for:` durations to `last_updated` for the muted attribute.

        Needed because the domain spec does not reflect that the condition
        reads from the muted and volume attributes.
        """
        return state.last_updated

    def _has_volume_attributes(self, state: State) -> bool:
        """Check if the state has volume muted or volume level attributes."""
        return (
            state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is not None
            or state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) is not None
        )

    def _should_include(self, state: State) -> bool:
        """Skip entities without volume attributes from the all/count check."""
        return super()._should_include(state) and self._has_volume_attributes(state)

    def _is_muted(self, state: State) -> bool:
        """Check if the media player is muted."""
        return (
            state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is True
            or state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == 0
        )

    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the entity state matches the targeted muted state."""
        if not self._has_volume_attributes(entity_state):
            return False
        return self._is_muted(entity_state) is self._target_muted


class MediaPlayerIsMutedCondition(_MediaPlayerMutedConditionBase):
    """Condition that passes when the media player is muted."""

    _target_muted = True


class MediaPlayerIsUnmutedCondition(_MediaPlayerMutedConditionBase):
    """Condition that passes when the media player is not muted."""

    _target_muted = False


class MediaPlayerIsVolumeCondition(EntityNumericalConditionBase):
    """Condition for media player volume level with 0.0-1.0 to percentage conversion."""

    _domain_specs = {DOMAIN: DomainSpec(value_source=ATTR_MEDIA_VOLUME_LEVEL)}
    _valid_unit = "%"

    def _get_tracked_value(self, entity_state: State) -> Any:
        """Get the volume value converted from 0.0-1.0 to percentage (0-100)."""
        raw = super()._get_tracked_value(entity_state)
        if raw is None:
            return None
        try:
            return float(raw) * 100.0
        except TypeError, ValueError:
            return None

    def _should_include(self, state: State) -> bool:
        """Skip media players that do not expose a volume_level attribute."""
        return (
            super()._should_include(state)
            and state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) is not None
        )


CONDITIONS: dict[str, type[Condition]] = {
    "is_muted": MediaPlayerIsMutedCondition,
    "is_not_playing": make_entity_state_condition(
        DOMAIN,
        {
            MediaPlayerState.BUFFERING,
            MediaPlayerState.IDLE,
            MediaPlayerState.OFF,
            MediaPlayerState.ON,
            MediaPlayerState.PAUSED,
        },
    ),
    "is_off": make_entity_state_condition(DOMAIN, MediaPlayerState.OFF),
    "is_on": make_entity_state_condition(
        DOMAIN,
        {
            MediaPlayerState.BUFFERING,
            MediaPlayerState.IDLE,
            MediaPlayerState.ON,
            MediaPlayerState.PAUSED,
            MediaPlayerState.PLAYING,
        },
    ),
    "is_paused": make_entity_state_condition(DOMAIN, MediaPlayerState.PAUSED),
    "is_playing": make_entity_state_condition(DOMAIN, MediaPlayerState.PLAYING),
    "is_unmuted": MediaPlayerIsUnmutedCondition,
    "is_volume": MediaPlayerIsVolumeCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for media players."""
    return CONDITIONS
