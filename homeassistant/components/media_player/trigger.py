"""Provides triggers for media players."""

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.trigger import EntityTriggerBase, Trigger

from . import MediaPlayerState
from .const import DOMAIN


class MediaPlayerStoppedPlayingTrigger(EntityTriggerBase):
    """Class for media player stopped playing trigger."""

    _domain: str = DOMAIN
    _from_states = {
        MediaPlayerState.BUFFERING,
        MediaPlayerState.PAUSED,
        MediaPlayerState.PLAYING,
    }
    _to_states = {
        MediaPlayerState.IDLE,
        MediaPlayerState.OFF,
        MediaPlayerState.ON,
    }

    def is_from_state(self, state: State) -> bool:
        """Check if the state matches the origin state."""
        return state.state in self._from_states

    def is_to_state(self, state: State) -> bool:
        """Check if the state matches the target state."""
        return state.state in self._to_states


TRIGGERS: dict[str, type[Trigger]] = {
    "stopped_playing": MediaPlayerStoppedPlayingTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for media players."""
    return TRIGGERS
