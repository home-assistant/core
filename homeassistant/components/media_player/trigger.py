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


class MediaPlayerMutedTrigger(EntityTriggerBase):
    """Class for media player muted triggers."""

    _domain_specs = {DOMAIN: DomainSpec()}

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

        return self.is_muted(from_state) != self.is_muted(to_state)

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state."""
        return self.is_muted(state)


TRIGGERS: dict[str, type[Trigger]] = {
    "muted": MediaPlayerMutedTrigger,
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
