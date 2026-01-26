"""Provides triggers for media players."""

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.trigger import (
    EntityTriggerBase,
    Trigger,
    make_entity_transition_trigger,
)

from . import ATTR_MEDIA_VOLUME_LEVEL, ATTR_MEDIA_VOLUME_MUTED, MediaPlayerState
from .const import DOMAIN


class MediaPlayerMutedTrigger(EntityTriggerBase):
    """Class for media player muted triggers."""

    _domain: str = DOMAIN

    def is_muted(self, state: State) -> bool:
        """Check if the media player is muted."""
        return (
            state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is True
            or state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == 0
        )

    def is_to_state(self, state: State) -> bool:
        """Check if the state matches the target state."""
        return self.is_muted(state)


TRIGGERS: dict[str, type[Trigger]] = {
    "muted": MediaPlayerMutedTrigger,
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
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for media players."""
    return TRIGGERS
