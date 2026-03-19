"""Tests for the WiiM media player via services and the state machine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wiim.consts import PlayingStatus
from wiim.models import (
    WiimGroupRole,
    WiimGroupSnapshot,
    WiimLoopState,
    WiimMediaMetadata,
    WiimPreset,
    WiimQueueItem,
    WiimQueueSnapshot,
    WiimRepeatMode,
    WiimTransportCapabilities,
)
from wiim.wiim_device import WiimDevice

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_BROWSE_MEDIA,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_SEEK,
    SERVICE_PLAY_MEDIA,
    SERVICE_REPEAT_SET,
    SERVICE_SELECT_SOURCE,
    SERVICE_SHUFFLE_SET,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    BrowseMedia,
    MediaClass,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import fire_general_update, fire_transport_update, setup_integration

from tests.common import MockConfigEntry

MEDIA_PLAYER_ENTITY_ID = "media_player.test_wiim_device"


async def test_state_machine_updates_from_device_callbacks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
) -> None:
    """Test cached device state is reflected in Home Assistant."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.state == MediaPlayerState.IDLE
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.5
    assert state.attributes[ATTR_INPUT_SOURCE] == "Network"
    assert state.attributes["supported_features"] == int(
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.GROUPING
        | MediaPlayerEntityFeature.SEEK
    )

    mock_wiim_device.volume = 60
    mock_wiim_device.playing_status = PlayingStatus.PLAYING
    mock_wiim_device.play_mode = "Bluetooth"
    mock_wiim_device.output_mode = "optical"
    mock_wiim_device.loop_state = WiimLoopState(
        repeat=WiimRepeatMode.ALL,
        shuffle=True,
    )
    mock_wiim_device.current_media = WiimMediaMetadata(
        title="New Song",
        artist="Test Artist",
        album="Test Album",
        uri="http://example.com/song.flac",
        duration=180,
        position=42,
    )
    mock_wiim_device.async_get_transport_capabilities.return_value = (
        WiimTransportCapabilities(
            can_next=True,
            can_previous=False,
            can_repeat=True,
            can_shuffle=True,
        )
    )

    await fire_general_update(hass, mock_wiim_device)

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.state == MediaPlayerState.PLAYING
    assert state.attributes[ATTR_MEDIA_TITLE] == "New Song"
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "Test Album"
    assert state.attributes[ATTR_MEDIA_DURATION] == 180
    assert state.attributes[ATTR_MEDIA_POSITION] == 42
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.6
    assert state.attributes[ATTR_INPUT_SOURCE] == "Bluetooth"
    assert state.attributes[ATTR_MEDIA_REPEAT] == RepeatMode.ALL
    assert state.attributes[ATTR_MEDIA_SHUFFLE] is True
    assert state.attributes["supported_features"] == int(
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.GROUPING
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.REPEAT_SET
        | MediaPlayerEntityFeature.SHUFFLE_SET
    )


async def test_state_machine_updates_from_transport_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
) -> None:
    """Test transport events update the state machine."""
    await setup_integration(hass, mock_config_entry)
    mock_wiim_device.current_media = WiimMediaMetadata(
        title="Queued Song",
        duration=240,
        position=30,
    )

    await fire_transport_update(hass, mock_wiim_device, PlayingStatus.PLAYING)
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.state == MediaPlayerState.PLAYING
    assert state.attributes[ATTR_MEDIA_TITLE] == "Queued Song"

    await fire_transport_update(hass, mock_wiim_device, PlayingStatus.PAUSED)
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.state == MediaPlayerState.PAUSED

    mock_wiim_device.current_media = None
    await fire_transport_update(hass, mock_wiim_device, PlayingStatus.STOPPED)
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.state == MediaPlayerState.IDLE
    assert state.attributes.get(ATTR_MEDIA_TITLE) is None


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "device_method",
        "expected_args",
        "state_update",
        "state_attr",
        "state_value",
    ),
    [
        (
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.75},
            "async_set_volume",
            (75,),
            {"volume": 75},
            ATTR_MEDIA_VOLUME_LEVEL,
            0.75,
        ),
        (
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: True},
            "async_set_mute",
            (True,),
            {"is_muted": True},
            ATTR_MEDIA_VOLUME_MUTED,
            True,
        ),
        (
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "Bluetooth"},
            "async_set_play_mode",
            ("Bluetooth",),
            {"play_mode": "Bluetooth"},
            ATTR_INPUT_SOURCE,
            "Bluetooth",
        ),
    ],
)
async def test_control_services_update_state_machine(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
    service: str,
    service_data: dict[str, object],
    device_method: str,
    expected_args: tuple[object, ...],
    state_update: dict[str, object],
    state_attr: str,
    state_value: object,
) -> None:
    """Test control services are exercised through Home Assistant."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, **service_data},
        blocking=True,
    )

    getattr(mock_wiim_device, device_method).assert_awaited_once_with(*expected_args)

    for attr_name, attr_value in state_update.items():
        setattr(mock_wiim_device, attr_name, attr_value)
    await fire_general_update(hass, mock_wiim_device)

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.attributes[state_attr] == state_value


async def test_repeat_and_shuffle_services_update_state_machine(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
) -> None:
    """Test repeat and shuffle go through services and state updates."""
    await setup_integration(hass, mock_config_entry)
    mock_wiim_device.async_get_transport_capabilities.return_value = (
        WiimTransportCapabilities(
            can_next=True,
            can_previous=True,
            can_repeat=True,
            can_shuffle=True,
        )
    )

    await fire_general_update(hass, mock_wiim_device)

    repeat_loop_mode = object()
    mock_wiim_device.build_loop_mode.return_value = repeat_loop_mode
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_MEDIA_REPEAT: RepeatMode.ALL},
        blocking=True,
    )
    mock_wiim_device.build_loop_mode.assert_called_once_with(WiimRepeatMode.ALL, False)
    mock_wiim_device.async_set_loop_mode.assert_awaited_once_with(repeat_loop_mode)

    mock_wiim_device.loop_state = WiimLoopState(
        repeat=WiimRepeatMode.ALL,
        shuffle=False,
    )
    await fire_general_update(hass, mock_wiim_device)
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_REPEAT] == RepeatMode.ALL

    mock_wiim_device.build_loop_mode.reset_mock()
    mock_wiim_device.async_set_loop_mode.reset_mock()
    shuffle_loop_mode = object()
    mock_wiim_device.build_loop_mode.return_value = shuffle_loop_mode
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_MEDIA_SHUFFLE: True},
        blocking=True,
    )
    mock_wiim_device.build_loop_mode.assert_called_once_with(WiimRepeatMode.ALL, True)
    mock_wiim_device.async_set_loop_mode.assert_awaited_once_with(shuffle_loop_mode)

    mock_wiim_device.loop_state = WiimLoopState(
        repeat=WiimRepeatMode.ALL,
        shuffle=True,
    )
    await fire_general_update(hass, mock_wiim_device)
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_SHUFFLE] is True


async def test_play_pause_and_seek_services_update_state_machine(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
) -> None:
    """Test playback services drive the device and state machine."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    mock_wiim_device.async_play.assert_awaited_once()

    mock_wiim_device.current_media = WiimMediaMetadata(
        title="Playing Song",
        duration=200,
        position=12,
    )
    mock_wiim_device.playing_status = PlayingStatus.PLAYING
    await fire_general_update(hass, mock_wiim_device)

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.state == MediaPlayerState.PLAYING
    assert state.attributes[ATTR_MEDIA_TITLE] == "Playing Song"

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    mock_wiim_device.async_pause.assert_awaited_once()
    mock_wiim_device.sync_device_duration_and_position.assert_awaited_once()

    await fire_transport_update(hass, mock_wiim_device, PlayingStatus.PAUSED)
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.state == MediaPlayerState.PAUSED

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_SEEK,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, "seek_position": 60},
        blocking=True,
    )
    mock_wiim_device.async_seek.assert_awaited_once_with(60)

    mock_wiim_device.current_media = WiimMediaMetadata(
        title="Playing Song",
        duration=200,
        position=60,
    )
    await fire_general_update(hass, mock_wiim_device)

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_POSITION] == 60


async def test_follower_routes_commands_and_reads_leader_metadata(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
) -> None:
    """Test follower commands are routed to the leader device."""
    await setup_integration(hass, mock_config_entry)
    leader_device = AsyncMock(spec=WiimDevice)
    leader_device.udn = "uuid:leader-1234"
    leader_device.name = "Leader WiiM Device"
    leader_device.playing_status = PlayingStatus.STOPPED
    leader_device.play_mode = "Network"
    leader_device.loop_state = WiimLoopState(
        repeat=WiimRepeatMode.OFF,
        shuffle=False,
    )
    leader_device.output_mode = "speaker"
    leader_device.current_media = None
    leader_device.async_get_transport_capabilities = AsyncMock(
        return_value=WiimTransportCapabilities(
            can_next=True,
            can_previous=False,
            can_repeat=True,
            can_shuffle=False,
        )
    )

    mock_wiim_controller.get_group_snapshot.return_value = WiimGroupSnapshot(
        role=WiimGroupRole.FOLLOWER,
        leader_udn=leader_device.udn,
        member_udns=(leader_device.udn, mock_wiim_device.udn),
    )
    mock_wiim_controller.get_device.side_effect = lambda udn: (
        leader_device if udn == leader_device.udn else mock_wiim_device
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    leader_device.async_play.assert_awaited_once()
    mock_wiim_device.async_play.assert_not_awaited()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_SEEK,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, "seek_position": 90},
        blocking=True,
    )
    leader_device.async_seek.assert_awaited_once_with(90)
    mock_wiim_device.async_seek.assert_not_awaited()

    leader_device.playing_status = PlayingStatus.PLAYING
    leader_device.play_mode = "Spotify"
    leader_device.current_media = WiimMediaMetadata(
        title="Leader Song",
        album="Leader Album",
        duration=210,
        position=90,
    )
    await fire_general_update(hass, mock_wiim_device)

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.state == MediaPlayerState.PLAYING
    assert state.attributes[ATTR_MEDIA_TITLE] == "Leader Song"
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "Leader Album"
    assert state.attributes[ATTR_INPUT_SOURCE] == "Spotify"
    assert state.attributes[ATTR_MEDIA_POSITION] == 90


async def test_follower_routes_repeat_shuffle_and_source_commands_to_leader(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
) -> None:
    """Test follower repeat, shuffle, and source changes are sent to the leader."""
    await setup_integration(hass, mock_config_entry)
    leader_device = AsyncMock(spec=WiimDevice)
    leader_device.udn = "uuid:leader-1234"
    leader_device.playing_status = PlayingStatus.STOPPED
    leader_device.current_media = None
    leader_device.loop_state = WiimLoopState(
        repeat=WiimRepeatMode.OFF,
        shuffle=False,
    )
    leader_device.play_mode = "Network"
    leader_device.async_get_transport_capabilities = AsyncMock(
        return_value=WiimTransportCapabilities(
            can_next=True,
            can_previous=True,
            can_repeat=True,
            can_shuffle=True,
        )
    )

    mock_wiim_controller.get_group_snapshot.return_value = WiimGroupSnapshot(
        role=WiimGroupRole.FOLLOWER,
        leader_udn=leader_device.udn,
        member_udns=(leader_device.udn, mock_wiim_device.udn),
    )
    mock_wiim_controller.get_device.side_effect = lambda udn: (
        leader_device if udn == leader_device.udn else mock_wiim_device
    )

    await fire_general_update(hass, mock_wiim_device)

    repeat_loop_mode = object()
    leader_device.build_loop_mode.return_value = repeat_loop_mode
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_MEDIA_REPEAT: RepeatMode.ALL},
        blocking=True,
    )
    leader_device.build_loop_mode.assert_called_once_with(WiimRepeatMode.ALL, False)
    leader_device.async_set_loop_mode.assert_awaited_once_with(repeat_loop_mode)
    mock_wiim_device.async_set_loop_mode.assert_not_awaited()

    leader_device.build_loop_mode.reset_mock()
    leader_device.async_set_loop_mode.reset_mock()
    shuffle_loop_mode = object()
    leader_device.build_loop_mode.return_value = shuffle_loop_mode
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_MEDIA_SHUFFLE: True},
        blocking=True,
    )
    leader_device.build_loop_mode.assert_called_once_with(WiimRepeatMode.OFF, True)
    leader_device.async_set_loop_mode.assert_awaited_once_with(shuffle_loop_mode)
    mock_wiim_device.async_set_loop_mode.assert_not_awaited()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_INPUT_SOURCE: "Bluetooth"},
        blocking=True,
    )
    leader_device.async_set_play_mode.assert_awaited_once_with("Bluetooth")
    mock_wiim_device.async_set_play_mode.assert_not_awaited()


async def test_play_media_services_call_device_commands(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
) -> None:
    """Test play_media services are driven through Home Assistant."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "1",
        },
        blocking=True,
    )
    mock_wiim_device.play_preset.assert_awaited_once_with(1)

    mock_wiim_device.current_media = WiimMediaMetadata(title="Preset 1")
    mock_wiim_device.playing_status = PlayingStatus.PLAYING
    await fire_general_update(hass, mock_wiim_device)
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.state == MediaPlayerState.PLAYING
    assert state.attributes[ATTR_MEDIA_TITLE] == "Preset 1"

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.TRACK,
            ATTR_MEDIA_CONTENT_ID: "2",
        },
        blocking=True,
    )
    mock_wiim_device.async_play_queue_with_index.assert_awaited_once_with(2)


@pytest.mark.parametrize("media_type", [MediaType.MUSIC, MediaType.URL])
async def test_play_media_url_service_uses_processed_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
    media_type: MediaType,
) -> None:
    """Test direct URL playback goes through the URL processor."""
    await setup_integration(hass, mock_config_entry)
    mock_wiim_device.supports_http_api = True

    with patch(
        "homeassistant.components.wiim.media_player.async_process_play_media_url",
        return_value="http://processed/song.mp3",
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: media_type,
                ATTR_MEDIA_CONTENT_ID: "http://example.com/song.mp3",
            },
            blocking=True,
        )

    mock_wiim_device.play_url.assert_awaited_once_with("http://processed/song.mp3")
    mock_wiim_device.play_preset.assert_not_awaited()


async def test_play_media_source_service_uses_resolved_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
) -> None:
    """Test media_source playback goes through the resolver."""
    await setup_integration(hass, mock_config_entry)
    mock_wiim_device.supports_http_api = True

    with (
        patch(
            "homeassistant.components.wiim.media_player.media_source.is_media_source_id",
            return_value=True,
        ),
        patch(
            "homeassistant.components.wiim.media_player.media_source.async_resolve_media",
            AsyncMock(return_value=MagicMock(url="http://resolved/song.mp3")),
        ),
        patch(
            "homeassistant.components.wiim.media_player.async_process_play_media_url",
            return_value="http://processed/song.mp3",
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/song.mp3",
            },
            blocking=True,
        )

    mock_wiim_device.play_url.assert_awaited_once_with("http://processed/song.mp3")


async def test_browse_media_service_returns_wiim_library(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
) -> None:
    """Test browsing WiiM presets and queue via the media_player service."""
    await setup_integration(hass, mock_config_entry)
    root_result = await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_BROWSE_MEDIA,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    root_browse = root_result[MEDIA_PLAYER_ENTITY_ID]
    assert root_browse.title == mock_wiim_device.name
    assert [child.title for child in root_browse.children] == ["Presets", "Queue"]

    mock_wiim_device.async_get_presets.return_value = (
        WiimPreset(1, "Preset 1", "http://image1"),
        WiimPreset(2, "Preset 2", "http://image2"),
    )
    preset_result = await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_BROWSE_MEDIA,
        {
            ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
            ATTR_MEDIA_CONTENT_ID: "wiim_library/library_root/favorites",
        },
        blocking=True,
        return_response=True,
    )
    preset_browse = preset_result[MEDIA_PLAYER_ENTITY_ID]
    assert [child.title for child in preset_browse.children] == ["Preset 1", "Preset 2"]

    mock_wiim_device.async_get_queue_snapshot.return_value = WiimQueueSnapshot(
        items=(
            WiimQueueItem(1, "Song A", "http://image-a"),
            WiimQueueItem(2, "Song B", "http://image-b"),
        ),
        is_active=True,
    )
    queue_result = await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_BROWSE_MEDIA,
        {
            ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
            ATTR_MEDIA_CONTENT_ID: "wiim_library/library_root/playlists",
        },
        blocking=True,
        return_response=True,
    )
    queue_browse = queue_result[MEDIA_PLAYER_ENTITY_ID]
    assert [child.title for child in queue_browse.children] == ["Song A", "Song B"]


async def test_browse_media_service_includes_media_sources_when_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: MagicMock,
    mock_wiim_controller: MagicMock,
) -> None:
    """Test media sources are exposed through browse_media when HTTP API exists."""
    await setup_integration(hass, mock_config_entry)
    mock_wiim_device.supports_http_api = True

    media_source_root = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="media-source://media_source",
        media_content_type=MediaType.APPS,
        title="Media Sources",
        can_play=False,
        can_expand=True,
        children=[
            BrowseMedia(
                media_class=MediaClass.MUSIC,
                media_content_id="media-source://media_source/local/song.mp3",
                media_content_type="audio/mpeg",
                title="song.mp3",
                can_play=True,
                can_expand=False,
            )
        ],
    )

    with patch(
        "homeassistant.components.wiim.media_player.media_source.async_browse_media",
        AsyncMock(return_value=media_source_root),
    ):
        result = await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_BROWSE_MEDIA,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
            blocking=True,
            return_response=True,
        )

    browse = result[MEDIA_PLAYER_ENTITY_ID]
    assert [child.title for child in browse.children] == [
        "Presets",
        "Queue",
        "song.mp3",
    ]
