"""Provides triggers for media players."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger, make_entity_transition_trigger

from . import MediaPlayerState
from .const import DOMAIN

TRIGGERS: dict[str, type[Trigger]] = {
    "paused_playing": make_conditional_entity_state_trigger(
        DOMAIN,
        from_states={
            MediaPlayerState.PLAYING,
        },
        to_states={
            MediaPlayerState.PAUSED,
        },
    ),
    "started_playing": make_conditional_entity_state_trigger(
        DOMAIN,
        from_states={
            MediaPlayerState.IDLE,
            MediaPlayerState.OFF,
            MediaPlayerState.ON,
            MediaPlayerState.PAUSED,
        },
        to_states={
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
    "turned_off": make_conditional_entity_state_trigger(
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
    "turned_on": make_conditional_entity_state_trigger(
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
