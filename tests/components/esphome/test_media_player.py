"""Test ESPHome media_players."""

from unittest.mock import AsyncMock, Mock, call, patch

from aioesphomeapi import (
    APIClient,
    MediaPlayerCommand,
    MediaPlayerEntityState,
    MediaPlayerInfo,
    MediaPlayerState,
)
import pytest

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import mock_platform
from tests.typing import WebSocketGenerator


async def test_media_player_entity(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic media_player entity."""
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
    state = hass.states.get("media_player.test_mymedia_player")
    assert state is not None
    assert state.state == "paused"

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: "media_player.test_mymedia_player",
            ATTR_MEDIA_VOLUME_MUTED: True,
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.MUTE)]
    )
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: "media_player.test_mymedia_player",
            ATTR_MEDIA_VOLUME_MUTED: True,
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.MUTE)]
    )
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: "media_player.test_mymedia_player",
            ATTR_MEDIA_VOLUME_LEVEL: 0.5,
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls([call(1, volume=0.5)])
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {
            ATTR_ENTITY_ID: "media_player.test_mymedia_player",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.PAUSE)]
    )
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {
            ATTR_ENTITY_ID: "media_player.test_mymedia_player",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.PLAY)]
    )
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {
            ATTR_ENTITY_ID: "media_player.test_mymedia_player",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.STOP)]
    )
    mock_client.media_player_command.reset_mock()


async def test_media_player_entity_with_source(
    hass: HomeAssistant,
    mock_client: APIClient,
    hass_ws_client: WebSocketGenerator,
    mock_generic_device_entry,
) -> None:
    """Test a generic media_player entity media source."""
    await async_setup_component(hass, "media_source", {"media_source": {}})
    await hass.async_block_till_done()
    esphome_platform_mock = Mock(
        async_get_media_browser_root_object=AsyncMock(
            return_value=[
                BrowseMedia(
                    title="Spotify",
                    media_class=MediaClass.APP,
                    media_content_id="",
                    media_content_type="spotify",
                    thumbnail="https://brands.home-assistant.io/_/spotify/logo.png",
                    can_play=False,
                    can_expand=True,
                )
            ]
        ),
        async_browse_media=AsyncMock(
            return_value=BrowseMedia(
                title="Spotify Favourites",
                media_class=MediaClass.PLAYLIST,
                media_content_id="",
                media_content_type="spotify",
                can_play=True,
                can_expand=False,
            )
        ),
        async_play_media=AsyncMock(return_value=False),
    )
    mock_platform(hass, "test.esphome", esphome_platform_mock)
    await async_setup_component(hass, "test", {"test": {}})
    await async_setup_component(hass, "media_source", {"media_source": {}})
    await hass.async_block_till_done()

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
            key=1, volume=50, muted=True, state=MediaPlayerState.PLAYING
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("media_player.test_mymedia_player")
    assert state is not None
    assert state.state == "playing"

    with pytest.raises(media_source.error.Unresolvable):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_mymedia_player",
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "media-source://local/xz",
            },
            blocking=True,
        )

    mock_client.media_player_command.reset_mock()

    play_media = media_source.PlayMedia(
        url="http://www.example.com/xy.mp3",
        mime_type="audio/mp3",
    )

    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=play_media,
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_mymedia_player",
                ATTR_MEDIA_CONTENT_TYPE: "audio/mp3",
                ATTR_MEDIA_CONTENT_ID: "media-source://local/xy",
            },
            blocking=True,
        )

    mock_client.media_player_command.assert_has_calls(
        [call(1, media_url="http://www.example.com/xy.mp3", announcement=None)]
    )

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_mymedia_player",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_mymedia_player",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.URL,
            ATTR_MEDIA_CONTENT_ID: "media-source://tts?message=hello",
            ATTR_MEDIA_ANNOUNCE: True,
        },
        blocking=True,
    )

    mock_client.media_player_command.assert_has_calls(
        [call(1, media_url="media-source://tts?message=hello", announcement=True)]
    )
