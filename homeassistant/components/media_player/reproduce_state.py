"""Module that groups code required to handle state restore for component."""

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.const import (
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    EntityStateAttribute,
)
from homeassistant.core import Context, HomeAssistant, State

from .const import (
    DOMAIN,
    MediaPlayerEntityFeature,
    MediaPlayerEntityStateAttribute,
    MediaPlayerService,
    MediaPlayerServiceArgument,
)

# Maps a state attribute to the service call argument used to restore it.
_STATE_ATTRIBUTE_TO_SERVICE_ARG: dict[MediaPlayerEntityStateAttribute, str] = {
    MediaPlayerEntityStateAttribute.INPUT_SOURCE: MediaPlayerServiceArgument.SOURCE,
    MediaPlayerEntityStateAttribute.SOUND_MODE: MediaPlayerServiceArgument.SOUND_MODE,
    MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL: MediaPlayerServiceArgument.VOLUME_LEVEL,
    MediaPlayerEntityStateAttribute.MEDIA_VOLUME_MUTED: MediaPlayerServiceArgument.IS_VOLUME_MUTED,
    MediaPlayerEntityStateAttribute.MEDIA_CONTENT_TYPE: MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE,
    MediaPlayerEntityStateAttribute.MEDIA_CONTENT_ID: MediaPlayerServiceArgument.MEDIA_CONTENT_ID,
}


async def _async_reproduce_states(
    hass: HomeAssistant,
    state: State,
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce component states."""
    cur_state = hass.states.get(state.entity_id)
    features = (
        cur_state.attributes[EntityStateAttribute.SUPPORTED_FEATURES]
        if cur_state
        else 0
    )

    async def call_service(
        service: str, attributes: Iterable[MediaPlayerEntityStateAttribute]
    ) -> None:
        """Call service with the given state attributes."""
        data = {"entity_id": state.entity_id}
        for attribute in attributes:
            if attribute in state.attributes:
                data[_STATE_ATTRIBUTE_TO_SERVICE_ARG[attribute]] = state.attributes[
                    attribute
                ]

        await hass.services.async_call(
            DOMAIN, service, data, blocking=True, context=context
        )

    if state.state == STATE_OFF:
        if features & MediaPlayerEntityFeature.TURN_OFF:
            await call_service(MediaPlayerService.TURN_OFF, [])
        # entities that are off have no other attributes to restore
        return

    if (
        state.state
        in (
            STATE_BUFFERING,
            STATE_IDLE,
            STATE_ON,
            STATE_PAUSED,
            STATE_PLAYING,
        )
        and features & MediaPlayerEntityFeature.TURN_ON
    ):
        await call_service(MediaPlayerService.TURN_ON, [])

    cur_state = hass.states.get(state.entity_id)
    features = (
        cur_state.attributes[EntityStateAttribute.SUPPORTED_FEATURES]
        if cur_state
        else 0
    )

    # First set source & sound mode to match the saved supported features
    if (
        MediaPlayerEntityStateAttribute.INPUT_SOURCE in state.attributes
        and features & MediaPlayerEntityFeature.SELECT_SOURCE
    ):
        await call_service(
            MediaPlayerService.SELECT_SOURCE,
            [MediaPlayerEntityStateAttribute.INPUT_SOURCE],
        )

    if (
        MediaPlayerEntityStateAttribute.SOUND_MODE in state.attributes
        and features & MediaPlayerEntityFeature.SELECT_SOUND_MODE
    ):
        await call_service(
            MediaPlayerService.SELECT_SOUND_MODE,
            [MediaPlayerEntityStateAttribute.SOUND_MODE],
        )

    if (
        MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL in state.attributes
        and features & MediaPlayerEntityFeature.VOLUME_SET
    ):
        await call_service(
            MediaPlayerService.VOLUME_SET,
            [MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL],
        )

    if (
        MediaPlayerEntityStateAttribute.MEDIA_VOLUME_MUTED in state.attributes
        and features & MediaPlayerEntityFeature.VOLUME_MUTE
    ):
        await call_service(
            MediaPlayerService.VOLUME_MUTE,
            [MediaPlayerEntityStateAttribute.MEDIA_VOLUME_MUTED],
        )

    already_playing = False

    if (MediaPlayerEntityStateAttribute.MEDIA_CONTENT_TYPE in state.attributes) and (
        MediaPlayerEntityStateAttribute.MEDIA_CONTENT_ID in state.attributes
    ):
        if features & MediaPlayerEntityFeature.PLAY_MEDIA:
            await call_service(
                MediaPlayerService.PLAY_MEDIA,
                [
                    MediaPlayerEntityStateAttribute.MEDIA_CONTENT_TYPE,
                    MediaPlayerEntityStateAttribute.MEDIA_CONTENT_ID,
                ],
            )
        already_playing = True

    if (
        not already_playing
        and state.state in (STATE_BUFFERING, STATE_PLAYING)
        and features & MediaPlayerEntityFeature.PLAY
    ):
        await call_service(MediaPlayerService.MEDIA_PLAY, [])
    elif state.state == STATE_IDLE:
        if features & MediaPlayerEntityFeature.STOP:
            await call_service(MediaPlayerService.MEDIA_STOP, [])
    elif state.state == STATE_PAUSED:
        if features & MediaPlayerEntityFeature.PAUSE:
            await call_service(MediaPlayerService.MEDIA_PAUSE, [])


async def async_reproduce_states(
    hass: HomeAssistant,
    states: Iterable[State],
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
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
