"""Provides triggers for media players."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger, make_entity_transition_trigger

from . import MediaPlayerState
from .const import DOMAIN

TRIGGERS: dict[str, type[Trigger]] = {
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
