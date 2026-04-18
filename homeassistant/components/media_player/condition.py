"""Provides conditions for media players."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition, make_entity_state_condition

from .const import DOMAIN, MediaPlayerState

CONDITIONS: dict[str, type[Condition]] = {
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
    "is_paused": make_entity_state_condition(DOMAIN, MediaPlayerState.PAUSED),
    "is_playing": make_entity_state_condition(DOMAIN, MediaPlayerState.PLAYING),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for media players."""
    return CONDITIONS
