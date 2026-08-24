"""Test ESPHome media_players."""

from unittest.mock import AsyncMock, Mock, call, patch

from aioesphomeapi import (
    APIClient,
    MediaPlayerCommand,
    MediaPlayerEntityState,
    MediaPlayerFormatPurpose,
    MediaPlayerInfo,
    MediaPlayerState,
    MediaPlayerSupportedFormat,
    UserService,
    build_device_unique_id,
)
import pytest

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_PLAYING,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    MockESPHomeDeviceType,
    MockGenericDeviceEntryType,
    reconnect_with_updated_entity_info,
)

from tests.common import mock_platform
from tests.typing import WebSocketGenerator

# PLAY_MEDIA,BROWSE_MEDIA,STOP,VOLUME_SET,
# VOLUME_MUTE,MEDIA_ANNOUNCE,PAUSE,PLAY
PROXY_FEATURE_FLAGS = 1200653


async def test_media_player_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic media_player entity."""
    entity_info = [
        MediaPlayerInfo(
            object_id="mymedia_player",
            key=1,
            name="my media_player",
            supports_pause=True,
            # PLAY_MEDIA,BROWSE_MEDIA,STOP,VOLUME_SET,
            # VOLUME_MUTE,MEDIA_ANNOUNCE,PAUSE,PLAY,
            # TURN_OFF,TURN_ON
            feature_flags=1201037,
        )
    ]
    states = [
        MediaPlayerEntityState(
            key=1, volume=50, muted=True, state=MediaPlayerState.PAUSED
        )
    ]
    user_service: list[UserService] = []
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
        [call(1, command=MediaPlayerCommand.MUTE, device_id=0)]
    )
    mock_client.media_player_command.reset_mock()

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
        [call(1, command=MediaPlayerCommand.MUTE, device_id=0)]
    )
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: "media_player.test_my_media_player",
            ATTR_MEDIA_VOLUME_LEVEL: 0.5,
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, volume=0.5, device_id=0)]
    )
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {
            ATTR_ENTITY_ID: "media_player.test_my_media_player",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.PAUSE, device_id=0)]
    )
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {
            ATTR_ENTITY_ID: "media_player.test_my_media_player",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.PLAY, device_id=0)]
    )
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {
            ATTR_ENTITY_ID: "media_player.test_my_media_player",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.STOP, device_id=0)]
    )
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "media_player.test_my_media_player",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.TURN_OFF, device_id=0)]
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "media_player.test_my_media_player",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.TURN_ON, device_id=0)]
    )
    mock_client.media_player_command.reset_mock()


async def test_media_player_entity_with_undefined_flags(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test that media_player handles undefined feature flags gracefully."""
    # Include existing flags (PAUSE=1, PLAY=16384, VOLUME_SET=4)
    # plus undefined bits (bit 6=64, bit 23=8388608)
    # Total: 1 + 16384 + 4 + 64 + 8388608 = 8405061
    entity_info = [
        MediaPlayerInfo(
            object_id="mymedia_player_undefined",
            key=1,
            name="my media_player undefined",
            supports_pause=True,
            # PAUSE,PLAY,VOLUME_SET + undefined bits 6 and 23
            feature_flags=8405061,
        )
    ]
    states = [
        MediaPlayerEntityState(
            key=1, volume=50, muted=False, state=MediaPlayerState.PLAYING
        )
    ]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    # Verify entity is created successfully despite undefined flags
    state = hass.states.get("media_player.test_my_media_player_undefined")
    assert state is not None
    assert state.state == STATE_PLAYING

    # Verify supported features only include known flags
    # Should have PAUSE, PLAY, and VOLUME_SET
    supported_features = state.attributes.get("supported_features", 0)
    # PAUSE=1, VOLUME_SET=4, PLAY=16384 = 16389
    assert supported_features == 16389

    # Verify entity works correctly with known features
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {
            ATTR_ENTITY_ID: "media_player.test_my_media_player_undefined",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.PLAY, device_id=0)]
    )
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {
            ATTR_ENTITY_ID: "media_player.test_my_media_player_undefined",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, command=MediaPlayerCommand.PAUSE, device_id=0)]
    )
    mock_client.media_player_command.reset_mock()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: "media_player.test_my_media_player_undefined",
            ATTR_MEDIA_VOLUME_LEVEL: 0.7,
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_has_calls(
        [call(1, volume=0.7, device_id=0)]
    )


async def test_media_player_entity_with_source(
    hass: HomeAssistant,
    mock_client: APIClient,
    hass_ws_client: WebSocketGenerator,
    mock_generic_device_entry: MockGenericDeviceEntryType,
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
                    thumbnail="/api/brands/integration/spotify/logo.png",
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
            supports_pause=True,
            feature_flags=PROXY_FEATURE_FLAGS,
        )
    ]
    states = [
        MediaPlayerEntityState(
            key=1, volume=50, muted=True, state=MediaPlayerState.PLAYING
        )
    ]
    user_service: list[UserService] = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("media_player.test_my_media_player")
    assert state is not None
    assert state.state == "playing"

    with pytest.raises(media_source.error.Unresolvable):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_my_media_player",
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
                ATTR_ENTITY_ID: "media_player.test_my_media_player",
                ATTR_MEDIA_CONTENT_TYPE: "audio/mp3",
                ATTR_MEDIA_CONTENT_ID: "media-source://local/xy",
            },
            blocking=True,
        )

    mock_client.media_player_command.assert_has_calls(
        [
            call(
                1,
                media_url="http://www.example.com/xy.mp3",
                announcement=None,
                device_id=0,
            )
        ]
    )

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_my_media_player",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_my_media_player",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.URL,
            ATTR_MEDIA_CONTENT_ID: "media-source://tts?message=hello",
            ATTR_MEDIA_ANNOUNCE: True,
        },
        blocking=True,
    )

    mock_client.media_player_command.assert_has_calls(
        [
            call(
                1,
                media_url="media-source://tts?message=hello",
                announcement=True,
                device_id=0,
            )
        ]
    )


async def test_media_player_proxy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a media_player entity with a proxy URL."""
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[
            MediaPlayerInfo(
                object_id="mymedia_player",
                key=1,
                name="my media_player",
                supports_pause=True,
                feature_flags=PROXY_FEATURE_FLAGS,
                supported_formats=[
                    MediaPlayerSupportedFormat(
                        format="flac",
                        sample_rate=0,  # source rate
                        num_channels=0,  # source channels
                        purpose=MediaPlayerFormatPurpose.DEFAULT,
                        sample_bytes=0,  # source width
                    ),
                    MediaPlayerSupportedFormat(
                        format="wav",
                        sample_rate=16000,
                        num_channels=1,
                        purpose=MediaPlayerFormatPurpose.ANNOUNCEMENT,
                        sample_bytes=2,
                    ),
                    MediaPlayerSupportedFormat(
                        format="mp3",
                        sample_rate=48000,
                        num_channels=2,
                        purpose=MediaPlayerFormatPurpose.DEFAULT,
                    ),
                ],
            )
        ],
        states=[
            MediaPlayerEntityState(
                key=1, volume=50, muted=False, state=MediaPlayerState.PAUSED
            )
        ],
    )
    await hass.async_block_till_done()
    dev = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, mock_device.entry.unique_id),
        mock_device.entry.entry_id,
    )
    assert dev is not None
    state = hass.states.get("media_player.test_my_media_player")
    assert state is not None
    assert state.state == "paused"

    media_url = "http://127.0.0.1/test.mp3"
    proxy_url = f"/api/esphome/ffmpeg_proxy/{dev.id}/test-id.flac"

    with (
        patch(
            "homeassistant.components.esphome.media_player.async_create_proxy_url",
            return_value=proxy_url,
        ) as mock_async_create_proxy_url,
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_my_media_player",
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: media_url,
            },
            blocking=True,
        )

        # Should be the default format
        mock_async_create_proxy_url.assert_called_once()
        device_id = mock_async_create_proxy_url.call_args[0][1]
        mock_async_create_proxy_url.assert_called_once_with(
            hass,
            device_id,
            media_url,
            media_format="flac",
            rate=None,
            channels=None,
            width=None,
        )

        media_args = mock_client.media_player_command.call_args.kwargs
        assert not media_args["announcement"]

        # Reset
        mock_async_create_proxy_url.reset_mock()

        # Set announcement flag
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_my_media_player",
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: media_url,
                ATTR_MEDIA_ANNOUNCE: True,
            },
            blocking=True,
        )

        # Should be the announcement format
        mock_async_create_proxy_url.assert_called_once()
        device_id = mock_async_create_proxy_url.call_args[0][1]
        mock_async_create_proxy_url.assert_called_once_with(
            hass,
            device_id,
            media_url,
            media_format="wav",
            rate=16000,
            channels=1,
            width=2,
        )

        media_args = mock_client.media_player_command.call_args.kwargs
        assert media_args["announcement"]

        # test with bypass_proxy flag
        mock_async_create_proxy_url.reset_mock()
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_my_media_player",
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: media_url,
                ATTR_MEDIA_EXTRA: {
                    "bypass_proxy": True,
                },
            },
            blocking=True,
        )
        mock_async_create_proxy_url.assert_not_called()
        media_args = mock_client.media_player_command.call_args.kwargs
        assert media_args["media_url"] == media_url


async def test_media_player_formats_reload_preserves_data(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test that media player formats are properly managed on reload."""
    # Create a media player with supported formats
    supported_formats = [
        MediaPlayerSupportedFormat(
            format="mp3",
            sample_rate=48000,
            num_channels=2,
            purpose=MediaPlayerFormatPurpose.DEFAULT,
        ),
        MediaPlayerSupportedFormat(
            format="wav",
            sample_rate=16000,
            num_channels=1,
            purpose=MediaPlayerFormatPurpose.ANNOUNCEMENT,
            sample_bytes=2,
        ),
    ]

    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[
            MediaPlayerInfo(
                object_id="test_media_player",
                key=1,
                name="Test Media Player",
                supports_pause=True,
                feature_flags=PROXY_FEATURE_FLAGS,
                supported_formats=supported_formats,
            )
        ],
        states=[
            MediaPlayerEntityState(
                key=1, volume=50, muted=False, state=MediaPlayerState.IDLE
            )
        ],
    )
    await hass.async_block_till_done()

    # Verify entity was created
    state = hass.states.get("media_player.test_Test_Media_Player")
    assert state is not None
    assert state.state == "idle"

    # Test that play_media works with proxy URL (which requires formats to be stored)
    media_url = "http://127.0.0.1/test.mp3"

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_Test_Media_Player",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: media_url,
        },
        blocking=True,
    )

    # Verify the API was called with a proxy URL (contains /api/esphome/ffmpeg_proxy/)
    mock_client.media_player_command.assert_called_once()
    call_args = mock_client.media_player_command.call_args
    assert "/api/esphome/ffmpeg_proxy/" in call_args.kwargs["media_url"]
    assert ".mp3" in call_args.kwargs["media_url"]  # Should use mp3 format for default
    assert call_args.kwargs["announcement"] is None

    mock_client.media_player_command.reset_mock()

    # Reload the integration
    await hass.config_entries.async_reload(mock_device.entry.entry_id)
    await hass.async_block_till_done()

    # Verify entity still exists after reload
    state = hass.states.get("media_player.test_Test_Media_Player")
    assert state is not None

    # Test that play_media still works after reload with announcement
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_Test_Media_Player",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: media_url,
            ATTR_MEDIA_ANNOUNCE: True,
        },
        blocking=True,
    )

    # Verify the API was called with a proxy URL using wav format for announcements
    mock_client.media_player_command.assert_called_once()
    call_args = mock_client.media_player_command.call_args
    assert "/api/esphome/ffmpeg_proxy/" in call_args.kwargs["media_url"]
    assert (
        ".wav" in call_args.kwargs["media_url"]
    )  # Should use wav format for announcement
    assert call_args.kwargs["announcement"] is True


async def test_media_player_formats_survive_rekey_onto_removed_entity_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test formats survive an entity taking over a removed entity's key.

    The removed media player briefly receives the surviving entity's
    info through the shared key before its teardown runs, so its
    cleanup must not delete the surviving entity's formats.
    """
    formats_one = [
        MediaPlayerSupportedFormat(
            format="mp3",
            sample_rate=48000,
            num_channels=2,
            purpose=MediaPlayerFormatPurpose.DEFAULT,
        ),
    ]
    formats_two = [
        MediaPlayerSupportedFormat(
            format="wav",
            sample_rate=16000,
            num_channels=1,
            purpose=MediaPlayerFormatPurpose.ANNOUNCEMENT,
            sample_bytes=2,
        ),
    ]
    entity_info = [
        MediaPlayerInfo(
            object_id="player_one",
            key=1,
            name="Player One",
            supports_pause=True,
            feature_flags=PROXY_FEATURE_FLAGS,
            supported_formats=formats_one,
        ),
        MediaPlayerInfo(
            object_id="player_two",
            key=2,
            name="Player Two",
            supports_pause=True,
            supported_formats=formats_two,
        ),
    ]
    states = [
        MediaPlayerEntityState(
            key=1, volume=50, muted=False, state=MediaPlayerState.IDLE
        ),
        MediaPlayerEntityState(
            key=2, volume=50, muted=False, state=MediaPlayerState.IDLE
        ),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    await hass.async_block_till_done()

    mac = device.device_info.mac_address
    unique_id_one = build_device_unique_id(mac, entity_info[0])
    unique_id_two = build_device_unique_id(mac, entity_info[1])

    # Player One takes over Player Two's key, Player Two is removed
    updated_entity_info = [
        MediaPlayerInfo(
            object_id="player_one",
            key=2,
            name="Player One",
            supports_pause=True,
            feature_flags=PROXY_FEATURE_FLAGS,
            supported_formats=formats_one,
        ),
    ]
    await reconnect_with_updated_entity_info(
        hass,
        device,
        updated_entity_info,
        states=[
            MediaPlayerEntityState(
                key=2, volume=50, muted=False, state=MediaPlayerState.IDLE
            )
        ],
    )

    assert (
        entity_registry.async_get_entity_id(
            MEDIA_PLAYER_DOMAIN, "esphome", unique_id_one
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(
            MEDIA_PLAYER_DOMAIN, "esphome", unique_id_two
        )
        is None
    )

    # The surviving entity's formats must not have been removed by the
    # removed entity's cleanup: playing media must still use the proxy
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player_one",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://127.0.0.1/test.mp3",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_called_once()
    call_args = mock_client.media_player_command.call_args
    assert "/api/esphome/ffmpeg_proxy/" in call_args.kwargs["media_url"]


async def test_media_player_formats_not_shared_with_sibling_taking_old_name(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test formats are not shared with a player adopting this one's old name.

    After a stable key rename the old name based unique_id is free; a
    new player claiming it must keep its own formats entry, or its
    formats would replace the renamed player's.
    """
    default_formats = [
        MediaPlayerSupportedFormat(
            format="mp3",
            sample_rate=48000,
            num_channels=2,
            purpose=MediaPlayerFormatPurpose.DEFAULT,
        ),
    ]
    announcement_formats = [
        MediaPlayerSupportedFormat(
            format="wav",
            sample_rate=16000,
            num_channels=1,
            purpose=MediaPlayerFormatPurpose.ANNOUNCEMENT,
            sample_bytes=2,
        ),
    ]
    entity_info = [
        MediaPlayerInfo(
            object_id="p_one",
            key=1,
            name="Alpha",
            supports_pause=True,
            feature_flags=PROXY_FEATURE_FLAGS,
            supported_formats=default_formats,
        ),
    ]
    states = [
        MediaPlayerEntityState(
            key=1, volume=50, muted=False, state=MediaPlayerState.IDLE
        ),
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    assert hass.states.get("media_player.test_alpha") is not None

    # Rename with a stable key, then a new player with announcement
    # only formats claims the old name
    renamed = MediaPlayerInfo(
        object_id="p_one",
        key=1,
        name="Beta",
        supports_pause=True,
        feature_flags=PROXY_FEATURE_FLAGS,
        supported_formats=default_formats,
    )
    new_player = MediaPlayerInfo(
        object_id="alpha",
        key=2,
        name="Alpha",
        supports_pause=True,
        feature_flags=PROXY_FEATURE_FLAGS,
        supported_formats=announcement_formats,
    )
    await reconnect_with_updated_entity_info(hass, device, [renamed])
    await reconnect_with_updated_entity_info(hass, device, [renamed, new_player])
    assert hass.states.get("media_player.test_alpha_2") is not None

    # The renamed player must still use its own default format proxy,
    # not the new player's announcement only formats
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_alpha",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://127.0.0.1/test.mp3",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_called_once()
    call_args = mock_client.media_player_command.call_args
    assert "/api/esphome/ffmpeg_proxy/" in call_args.kwargs["media_url"]
    assert ".mp3" in call_args.kwargs["media_url"]
    mock_client.media_player_command.reset_mock()

    # The new player has no default format, so it must not proxy; a
    # shared formats entry would hand it the renamed player's mp3
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_alpha_2",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://127.0.0.1/test.mp3",
        },
        blocking=True,
    )
    mock_client.media_player_command.assert_called_once()
    call_args = mock_client.media_player_command.call_args
    assert call_args.kwargs["media_url"] == "http://127.0.0.1/test.mp3"
