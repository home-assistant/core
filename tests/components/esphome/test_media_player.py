"""Test ESPHome media_players."""


from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    MediaPlayerCommand,
    MediaPlayerEntityState,
    MediaPlayerInfo,
    MediaPlayerState,
)

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_VOLUME_MUTE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_media_player_entity_no_open(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic media_player entity that does not support open."""
    entity_info = [
        MediaPlayerInfo(
            object_id="mymedia_player",
            key=1,
            name="my media_player",
            unique_id="my_media_player",
            supports_pause=True,
        )
    ]
    states = [
        MediaPlayerEntityState(
            key=1, volume=50, muted=True, state=MediaPlayerState.PAUSED
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("media_player.test_my_media_player")
    assert state is not None
    assert state.state == "paused"

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: "media_player.test_my_media_player",
            ATTR_MEDIA_VOLUME_MUTED: True,
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.MUTE)]
    )
    mock_client.media_player_command.reset_mock()
