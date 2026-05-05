"""Provides triggers for media players."""

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    EntityTriggerBase,
    Trigger,
    make_entity_transition_trigger,
)

from . import ATTR_MEDIA_VOLUME_LEVEL, ATTR_MEDIA_VOLUME_MUTED, MediaPlayerState
from .const import DOMAIN


class _MediaPlayerMutedStateTriggerBase(EntityTriggerBase):
    """Base class for media player muted/unmuted triggers."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _target_muted: bool

    def _has_volume_attributes(self, state: State) -> bool:
        """Check if the state has volume muted or volume level attributes."""
        return (
            state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is not None
            or state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) is not None
        )

    def _should_include(self, state: State) -> bool:
        """Check if an entity should participate in all/count checks.

        Entities without volume attributes cannot be muted, so they are
        excluded from the check - otherwise an "all" check would never
        pass when there are media players without volume support.
        """
        return state.state not in self._excluded_states and self._has_volume_attributes(
            state
        )

    def check_all_match(self, entity_ids: set[str]) -> bool:
        """Check if all mutable entity states match."""
        return all(
            self.is_valid_state(state)
            for entity_id in entity_ids
            if (state := self._hass.states.get(entity_id)) is not None
            and self._should_include(state)
        )

    def count_matches(self, entity_ids: set[str]) -> int:
        """Count matching mutable entities."""
        return sum(
            self.is_valid_state(state)
            for entity_id in entity_ids
            if (state := self._hass.states.get(entity_id)) is not None
            and self._should_include(state)
        )

    def is_muted(self, state: State) -> bool:
        """Check if the media player is muted."""
        return (
            state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is True
            or state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == 0
        )

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False

        if not self._has_volume_attributes(to_state):
            return False

        return self.is_muted(from_state) != self.is_muted(to_state)

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state."""
        if not self._has_volume_attributes(state):
            return False
        return self.is_muted(state) is self._target_muted


class MediaPlayerMutedTrigger(_MediaPlayerMutedStateTriggerBase):
    """Class for media player muted triggers."""

    _target_muted = True


class MediaPlayerUnmutedTrigger(_MediaPlayerMutedStateTriggerBase):
    """Class for media player unmuted triggers."""

    _target_muted = False


TRIGGERS: dict[str, type[Trigger]] = {
    "muted": MediaPlayerMutedTrigger,
    "unmuted": MediaPlayerUnmutedTrigger,
    "paused_playing": make_entity_transition_trigger(
        DOMAIN,
        from_states={
            MediaPlayerState.BUFFERING,
            MediaPlayerState.PLAYING,
        },
        to_states={
            MediaPlayerState.PAUSED,
        },
    ),
    "started_playing": make_entity_transition_trigger(
        DOMAIN,
        from_states={
            MediaPlayerState.IDLE,
            MediaPlayerState.OFF,
            MediaPlayerState.ON,
            MediaPlayerState.PAUSED,
        },
        to_states={
            MediaPlayerState.BUFFERING,
            MediaPlayerState.PLAYING,
        },
    ),
    "stopped_playing": make_entity_transition_trigger(
        DOMAIN,
        from_states={
            MediaPlayerState.BUFFERING,
            MediaPlayerState.PAUSED,
            MediaPlayerState.PLAYING,
        },
        to_states={
            MediaPlayerState.IDLE,
            MediaPlayerState.OFF,
            MediaPlayerState.ON,
        },
    ),
    "turned_off": make_entity_transition_trigger(
        DOMAIN,
        from_states={
            MediaPlayerState.BUFFERING,
            MediaPlayerState.IDLE,
            MediaPlayerState.ON,
            MediaPlayerState.PAUSED,
            MediaPlayerState.PLAYING,
        },
        to_states={
            MediaPlayerState.OFF,
        },
    ),
    "turned_on": make_entity_transition_trigger(
        DOMAIN,
        from_states={
            MediaPlayerState.OFF,
        },
        to_states={
            MediaPlayerState.BUFFERING,
            MediaPlayerState.IDLE,
            MediaPlayerState.ON,
            MediaPlayerState.PAUSED,
            MediaPlayerState.PLAYING,
        },
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for media players."""
    return TRIGGERS
