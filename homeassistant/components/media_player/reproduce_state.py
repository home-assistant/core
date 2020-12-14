"""Module that groups code required to handle state restore for component."""
import asyncio
from typing import Any, Dict, Iterable, Optional

from homeassistant.const import (
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import Context, State
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
)

# mypy: allow-untyped-defs


async def _async_reproduce_states(
    hass: HomeAssistantType,
    state: State,
    *,
    context: Optional[Context] = None,
    reproduce_options: Optional[Dict[str, Any]] = None,
) -> None:
    """Reproduce component states."""

    async def call_service(service: str, keys: Iterable) -> None:
        """Call service with set of attributes given."""
        data = {"entity_id": state.entity_id}
        for key in keys:
            if key in state.attributes:
                data[key] = state.attributes[key]

        await hass.services.async_call(
            DOMAIN, service, data, blocking=True, context=context
        )

    if state.state == STATE_OFF:
        await call_service(SERVICE_TURN_OFF, [])
        # entities that are off have no other attributes to restore
        return

    if state.state in [
        STATE_ON,
        STATE_PLAYING,
        STATE_IDLE,
        STATE_PAUSED,
    ]:
        await call_service(SERVICE_TURN_ON, [])

    if ATTR_MEDIA_VOLUME_LEVEL in state.attributes:
        await call_service(SERVICE_VOLUME_SET, [ATTR_MEDIA_VOLUME_LEVEL])

    if ATTR_MEDIA_VOLUME_MUTED in state.attributes:
        await call_service(SERVICE_VOLUME_MUTE, [ATTR_MEDIA_VOLUME_MUTED])

    if ATTR_INPUT_SOURCE in state.attributes:
        await call_service(SERVICE_SELECT_SOURCE, [ATTR_INPUT_SOURCE])

    if ATTR_SOUND_MODE in state.attributes:
        await call_service(SERVICE_SELECT_SOUND_MODE, [ATTR_SOUND_MODE])

    already_playing = False

    if (ATTR_MEDIA_CONTENT_TYPE in state.attributes) and (
        ATTR_MEDIA_CONTENT_ID in state.attributes
    ):
        await call_service(
            SERVICE_PLAY_MEDIA,
            [ATTR_MEDIA_CONTENT_TYPE, ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_ENQUEUE],
        )
        already_playing = True

    if state.state == STATE_PLAYING and not already_playing:
        await call_service(SERVICE_MEDIA_PLAY, [])
    elif state.state == STATE_IDLE:
        await call_service(SERVICE_MEDIA_STOP, [])
    elif state.state == STATE_PAUSED:
        await call_service(SERVICE_MEDIA_PAUSE, [])


async def async_reproduce_states(
    hass: HomeAssistantType,
    states: Iterable[State],
    *,
    context: Optional[Context] = None,
    reproduce_options: Optional[Dict[str, Any]] = None,
) -> None:
    """Reproduce component states."""
    await asyncio.gather(
        *(
            _async_reproduce_states(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
