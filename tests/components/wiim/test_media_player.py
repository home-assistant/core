"""pytest media_player.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wiim.consts import InputMode, PlayingStatus
from wiim.wiim_device import WiimDevice

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.components.wiim.const import DOMAIN, WiimData
from homeassistant.components.wiim.media_player import (
    MEDIA_CONTENT_ID_FAVORITES,
    MEDIA_CONTENT_ID_PLAYLISTS,
    MEDIA_CONTENT_ID_ROOT,
    MEDIA_TYPE_WIIM_LIBRARY,
    SDK_TO_HA_STATE,
    SUPPORT_WIIM_BASE,
    WiimMediaPlayerEntity,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_media_player_setup_entry(
    mock_hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_wiim_device: WiimDevice,
    mock_add_entities: AsyncMock,
) -> None:
    """Test the media player setup entry."""
    mock_config_entry.runtime_data = mock_wiim_device
    mock_hass.data = {
        DOMAIN: WiimData(
            controller=MagicMock(),
            entity_id_to_udn_map={},
        )
    }  # type: ignore[assignment]
    await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1
    entity = entities[0]
    assert isinstance(entity, WiimMediaPlayerEntity)
    assert entity._device is mock_wiim_device


@pytest.mark.asyncio
async def test_media_player_attributes(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity, mock_wiim_device: WiimDevice
) -> None:
    """Test media player entity attributes."""
    entity = mock_wiim_media_player_entity
    entity._device = mock_wiim_device
    entity._attr_name = mock_wiim_device.name  # type: ignore[assignment]
    entity._attr_unique_id = f"{mock_wiim_device.udn}-media_player"
    entity._attr_device_info = {
        "identifiers": {(DOMAIN, mock_wiim_device.udn)},
        "name": mock_wiim_device.name,
    }
    entity._attr_supported_features = SUPPORT_WIIM_BASE
    entity._attr_device_class = MediaPlayerDeviceClass.SPEAKER
    entity._attr_state = SDK_TO_HA_STATE.get(mock_wiim_device.playing_status)
    entity._attr_volume_level = mock_wiim_device.volume / 100
    entity._attr_is_volume_muted = mock_wiim_device.is_muted
    entity._attr_repeat = RepeatMode.OFF
    entity._attr_source = InputMode.LINE_IN.display_name  # type: ignore[attr-defined]

    assert entity.unique_id == f"{mock_wiim_device.udn}-media_player"
    assert entity.name == mock_wiim_device.name
    assert entity.device_info is not None
    assert entity.device_info["identifiers"] == {(DOMAIN, mock_wiim_device.udn)}
    assert entity.device_info["name"] == mock_wiim_device.name
    assert entity.supported_features == SUPPORT_WIIM_BASE
    assert entity.device_class == MediaPlayerDeviceClass.SPEAKER

    assert entity.state == SDK_TO_HA_STATE.get(mock_wiim_device.playing_status)
    assert entity.volume_level == mock_wiim_device.volume / 100
    assert entity.is_volume_muted == mock_wiim_device.is_muted
    assert entity.repeat == RepeatMode.OFF
    assert entity.source == InputMode.LINE_IN.display_name  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_media_player_update_ha_state_from_sdk_cache(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test _update_ha_state_from_sdk_cache schedules HA state update."""
    entity = mock_wiim_media_player_entity
    mock_hass.data = {
        DOMAIN: WiimData(
            controller=MagicMock(),
            entity_id_to_udn_map={},
        )
    }  # type: ignore[assignment]

    entity.hass = mock_hass

    mock_wiim_device.playing_status = PlayingStatus.PLAYING
    mock_wiim_device.volume = 60  # 0.6
    mock_wiim_device.current_track_info = {"title": "New Song"}
    mock_wiim_device.available = True  # type: ignore[misc]

    entity._device = mock_wiim_device
    entity.entity_id = "media_player.test_device"
    entity._attr_group_members = ["media_player.test_device", "media_player.follower1"]

    follower_entity = MagicMock()
    follower_entity.entity_id = "media_player.follower1"
    follower_entity._async_apply_leader_metadata = AsyncMock()

    with (
        patch.object(entity, "schedule_update_ha_state", new=MagicMock()),
        patch.object(entity, "async_write_ha_state", new=AsyncMock()),
        patch.object(
            entity.hass.data[DOMAIN].controller,
            "get_device_group_info",
            new=MagicMock(return_value={"role": "leader"}),
        ),
    ):
        entity._update_ha_state_from_sdk_cache()

        assert entity.state == MediaPlayerState.PLAYING
        assert entity.volume_level == 0.6
        assert entity.media_title == "New Song"


@pytest.mark.asyncio
async def test_media_player_play(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player play service."""
    entity = mock_wiim_media_player_entity

    mock_hass.data = {
        DOMAIN: WiimData(
            controller=MagicMock(),
            entity_id_to_udn_map={},
        )
    }  # type: ignore[assignment]

    entity.hass = mock_hass

    with patch.object(
        mock_wiim_device, "async_play", new_callable=AsyncMock
    ) as mock_play:
        await entity.async_media_play()
        mock_play.assert_awaited_once()


@pytest.mark.asyncio
async def test_media_player_pause(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player pause service."""
    entity = mock_wiim_media_player_entity

    mock_hass.data = {
        DOMAIN: WiimData(
            controller=MagicMock(),
            entity_id_to_udn_map={},
        )
    }  # type: ignore[assignment]

    entity.hass = mock_hass
    entity._device = mock_wiim_device

    mock_wiim_device.async_set_AVT_cmd = AsyncMock(
        return_value={"RelTime": "00:00:10", "TrackDuration": "00:03:30"}
    )
    mock_wiim_device.parse_duration = MagicMock(
        side_effect=lambda s: 10 if s == "00:00:10" else 210
    )

    with patch.object(
        mock_wiim_device, "async_pause", new_callable=AsyncMock
    ) as mock_pause:
        await entity.async_media_pause()
        mock_pause.assert_awaited_once()


@pytest.mark.asyncio
async def test_media_player_stop(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player stop service."""
    entity = mock_wiim_media_player_entity

    mock_hass.data = {
        DOMAIN: WiimData(
            controller=MagicMock(),
            entity_id_to_udn_map={},
        )
    }  # type: ignore[assignment]

    entity.hass = mock_hass
    with patch.object(
        mock_wiim_device, "async_stop", new_callable=AsyncMock
    ) as mock_stop:
        await entity.async_media_stop()
        mock_stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_media_player_set_volume(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player set volume service."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    with patch.object(
        mock_wiim_device, "async_set_volume", new_callable=AsyncMock
    ) as mock_set_volume:
        await entity.async_set_volume_level(0.75)
        mock_set_volume.assert_awaited_once_with(75)


@pytest.mark.asyncio
async def test_media_player_mute_volume(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player mute volume service."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    with patch.object(
        mock_wiim_device, "async_set_mute", new_callable=AsyncMock
    ) as mock_set_mute:
        await entity.async_mute_volume(True)
        mock_set_mute.assert_awaited_once_with(True)


@pytest.mark.asyncio
async def test_media_player_play_media_url(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity, mock_wiim_device: WiimDevice
) -> None:
    """Test media player play media service with a URL."""
    entity = mock_wiim_media_player_entity
    mock_wiim_device.supports_http_api = True
    entity._device = mock_wiim_device

    with patch.object(
        mock_wiim_device, "play_preset", new_callable=AsyncMock
    ) as mock_http_cmd_ok:
        await entity.async_play_media(MediaType.MUSIC, "1")
        mock_http_cmd_ok.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_media_player_select_source(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player select source service."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass

    with patch.object(
        mock_wiim_device, "async_set_play_mode", new_callable=AsyncMock
    ) as mock_play_mode:
        await entity.async_select_source("Bluetooth")
        mock_play_mode.assert_awaited_once()


@pytest.mark.asyncio
async def test_media_player_select_sound_mode(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player select sound mode service."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass

    with patch.object(
        mock_wiim_device, "async_set_output_mode", new_callable=AsyncMock
    ) as mock_output_mode:
        await entity.async_select_sound_mode("Jazz")
        mock_output_mode.assert_awaited_once()


@pytest.mark.asyncio
async def test_media_player_seek(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player seek service."""
    entity = mock_wiim_media_player_entity

    mock_hass.data = {
        DOMAIN: WiimData(
            controller=MagicMock(),
            entity_id_to_udn_map={},
        )
    }  # type: ignore[assignment]

    entity.hass = mock_hass

    with patch.object(
        mock_wiim_device, "async_seek", new_callable=AsyncMock
    ) as mock_seek:
        await entity.async_media_seek(60)
        mock_seek.assert_awaited_once_with(60)


@pytest.mark.asyncio
async def test_media_player_next(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player next track service."""
    entity = mock_wiim_media_player_entity

    mock_hass.data = {
        DOMAIN: WiimData(
            controller=MagicMock(),
            entity_id_to_udn_map={},
        )
    }  # type: ignore[assignment]

    entity.hass = mock_hass

    with patch.object(
        mock_wiim_device, "async_next", new_callable=AsyncMock
    ) as mock_next:
        await entity.async_media_next_track()
        mock_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_media_player_previous(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player previous track service."""
    entity = mock_wiim_media_player_entity

    mock_hass.data = {
        DOMAIN: WiimData(
            controller=MagicMock(),
            entity_id_to_udn_map={},
        )
    }  # type: ignore[assignment]

    entity.hass = mock_hass

    with patch.object(
        mock_wiim_device, "async_previous", new_callable=AsyncMock
    ) as mock_previous:
        await entity.async_media_previous_track()
        mock_previous.assert_awaited_once()


@pytest.mark.asyncio
async def test_media_player_set_repeat_mode(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player set repeat mode service."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    with patch.object(
        mock_wiim_device, "async_set_loop_mode", new_callable=AsyncMock
    ) as mock_loop_mode:
        await entity.async_set_repeat(RepeatMode.ALL)
        mock_loop_mode.assert_awaited_once()
        mock_loop_mode.reset_mock()

        await entity.async_set_repeat(RepeatMode.OFF)
        mock_loop_mode.assert_awaited_once()
        mock_loop_mode.reset_mock()

        await entity.async_set_repeat(RepeatMode.ONE)
        mock_loop_mode.assert_awaited_once()
        mock_loop_mode.reset_mock()


@pytest.mark.asyncio
async def test_media_player_browse_media_root(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test Browse root media."""
    entity = mock_wiim_media_player_entity
    mock_controller = MagicMock()
    mock_controller.async_ungroup_device = AsyncMock()
    mock_controller.async_join_group = AsyncMock()
    mock_controller.async_update_multiroom_status = AsyncMock()
    mock_hass.data = {
        DOMAIN: WiimData(
            controller=mock_controller,
            entity_id_to_udn_map={"media_player.other_wiim_device": "uuid:target-456"},
        ),
        "media_source": {},
    }  # type: ignore[assignment]
    entity.hass = mock_hass

    mock_browse_item = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="mock_id",
        media_content_type=MediaType.MUSIC,
        title="Mock Source",
        can_play=False,
        can_expand=True,
        children=[],
    )

    with patch(
        "homeassistant.components.media_source.async_browse_media",
        AsyncMock(return_value=mock_browse_item),
    ):
        browse_result = await entity.async_browse_media(MEDIA_CONTENT_ID_ROOT)

    assert browse_result.media_class == MediaClass.DIRECTORY
    assert browse_result.media_content_id == MEDIA_CONTENT_ID_ROOT
    assert browse_result.media_content_type == MEDIA_TYPE_WIIM_LIBRARY
    assert browse_result.title == mock_wiim_device.name
    assert browse_result.can_play is False
    assert browse_result.can_expand is True
    assert browse_result.children is not None
    assert len(browse_result.children) == 2
    assert browse_result.children[0].title == "Presets"
    assert browse_result.children[1].title == "Queue"


@pytest.mark.asyncio
async def test_media_player_browse_media_favorites(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity, mock_wiim_device: WiimDevice
) -> None:
    """Test Browse favorites (presets)."""
    entity = mock_wiim_media_player_entity
    with patch.object(
        mock_wiim_device, "async_get_favorites", new_callable=AsyncMock
    ) as mock_fav:
        mock_fav.return_value = [
            {"name": "Preset 1", "uri": "preset_1", "image_url": "http://image1.jpg"},
            {"name": "Preset 2", "uri": "preset_2", "image_url": "http://image2.jpg"},
        ]

        browse_result = await entity.async_browse_media(
            MediaType.PLAYLIST, MEDIA_CONTENT_ID_FAVORITES
        )

        assert browse_result.media_class == MediaClass.PLAYLIST
        assert browse_result.media_content_id == MEDIA_CONTENT_ID_FAVORITES
        assert browse_result.media_content_type == MediaType.PLAYLIST
        assert browse_result.title == "Presets"
        assert browse_result.can_play is False
        assert browse_result.can_expand is True
        assert browse_result.children is not None
        assert len(browse_result.children) == 2

        child_item = browse_result.children[0]
        assert child_item.media_class == MediaClass.PLAYLIST
        assert child_item.media_content_id == "preset_1"
        assert child_item.media_content_type == MediaType.MUSIC
        assert child_item.title == "Preset 1"
        assert child_item.can_play is True
        assert child_item.can_expand is False
        assert child_item.thumbnail == "http://image1.jpg"


@pytest.mark.asyncio
async def test_media_player_browse_media_playlists_queue(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity, mock_wiim_device: WiimDevice
) -> None:
    """Test browsing media playlists queues for the Wiim media player entity."""
    entity = mock_wiim_media_player_entity

    with (
        patch.object(
            mock_wiim_device, "async_get_queue_items", new_callable=AsyncMock
        ) as mock_get_queue_items,
        patch.object(
            mock_wiim_device, "async_set_AVT_cmd", new_callable=AsyncMock
        ) as mock_set_AVT_cmd,
    ):
        mock_get_queue_items.return_value = [
            {"SourceName": "SPOTIFY"},
            {
                "name": "Song A",
                "image_url": "Artist A",
                "uri": "1",
                "SourceName": "SPOTIFY",
            },
            {"name": "Song B", "image_url": "Artist B", "uri": "2"},
        ]

        mock_set_AVT_cmd.return_value = {
            "PlayMedium": "SONGLIST-NETWORK",
            "TrackSource": "SPOTIFY",
        }

        browse_result = await entity.async_browse_media(
            MediaType.PLAYLIST, MEDIA_CONTENT_ID_PLAYLISTS
        )

        assert browse_result.media_class == MediaClass.PLAYLIST
        assert browse_result.media_content_id == MEDIA_CONTENT_ID_PLAYLISTS
        assert browse_result.media_content_type == MediaType.PLAYLIST
        assert browse_result.title == "Queue"
        assert browse_result.can_play is False
        assert browse_result.can_expand is True

        assert browse_result.children is not None
        assert len(browse_result.children) == 2

        child_item = browse_result.children[0]
        assert child_item.media_class == MediaClass.TRACK
        assert child_item.media_content_id == "1"
        assert child_item.media_content_type == MediaType.TRACK
        assert child_item.title == "Song A"
        assert child_item.can_play is True
        assert child_item.can_expand is False

        mock_get_queue_items.assert_awaited_once()
        mock_set_AVT_cmd.assert_awaited_once()
