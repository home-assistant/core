"""Tests for the WiiM media player entity."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wiim.consts import InputMode, PlayingStatus
from wiim.exceptions import WiimException, WiimRequestException
from wiim.models import (
    WiimGroupRole,
    WiimMediaMetadata,
    WiimPreset,
    WiimQueueItem,
    WiimQueueSnapshot,
    WiimRepeatMode,
    WiimTransportCapabilities,
)
from wiim.wiim_device import WiimDevice

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.components.wiim.const import DATA_WIIM, DOMAIN
from homeassistant.components.wiim.media_player import (
    MEDIA_CONTENT_ID_FAVORITES,
    MEDIA_CONTENT_ID_PLAYLISTS,
    MEDIA_CONTENT_ID_ROOT,
    MEDIA_TYPE_WIIM_LIBRARY,
    SUPPORT_WIIM_BASE,
    WiimMediaPlayerEntity,
    async_process_play_media_url,
    async_setup_entry,
)
from homeassistant.components.wiim.models import WiimData
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity import Entity, EntityPlatformState


def _set_wiim_data(
    hass: HomeAssistant,
    *,
    controller: MagicMock | None = None,
    entity_id_to_udn_map: dict[str, str] | None = None,
) -> None:
    """Populate the typed WiiM domain data for a test Home Assistant instance."""
    hass.data[DATA_WIIM] = WiimData(
        controller=controller or MagicMock(),
        entity_id_to_udn_map=entity_id_to_udn_map or {},
    )


async def test_media_player_setup_entry(
    mock_hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_wiim_device: WiimDevice,
    mock_add_entities: AsyncMock,
) -> None:
    """Test the media player setup entry."""
    mock_config_entry.runtime_data = mock_wiim_device
    _set_wiim_data(mock_hass)
    await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)

    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1
    entity = entities[0]
    assert isinstance(entity, WiimMediaPlayerEntity)
    assert entity._device is mock_wiim_device


async def test_media_player_attributes(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity, mock_wiim_device: WiimDevice
) -> None:
    """Test media player entity attributes."""
    entity = mock_wiim_media_player_entity
    entity._device = mock_wiim_device
    entity._attr_name = mock_wiim_device.name  # type: ignore[assignment]
    entity._attr_unique_id = mock_wiim_device.udn
    entity._attr_device_info = {
        "identifiers": {(DOMAIN, mock_wiim_device.udn)},
        "name": mock_wiim_device.name,
    }
    entity._transport_capabilities = None
    entity._attr_device_class = MediaPlayerDeviceClass.SPEAKER
    entity._attr_state = MediaPlayerState.IDLE
    entity._attr_volume_level = mock_wiim_device.volume / 100
    entity._attr_is_volume_muted = mock_wiim_device.is_muted
    entity._attr_repeat = RepeatMode.OFF
    entity._attr_source = InputMode.LINE_IN.display_name  # type: ignore[attr-defined]

    assert entity.unique_id == mock_wiim_device.udn
    assert entity.name == mock_wiim_device.name
    assert entity.device_info is not None
    assert entity.device_info["identifiers"] == {(DOMAIN, mock_wiim_device.udn)}
    assert entity.device_info["name"] == mock_wiim_device.name
    assert entity.supported_features == SUPPORT_WIIM_BASE
    assert entity.device_class == MediaPlayerDeviceClass.SPEAKER

    assert entity.state == MediaPlayerState.IDLE
    assert entity.volume_level == mock_wiim_device.volume / 100
    assert entity.is_volume_muted == mock_wiim_device.is_muted
    assert entity.repeat == RepeatMode.OFF
    assert entity.source == InputMode.LINE_IN.display_name  # type: ignore[attr-defined]


async def test_media_player_update_ha_state_from_sdk_cache(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test _update_ha_state_from_sdk_cache schedules HA state update."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)

    entity.hass = mock_hass

    mock_wiim_device.playing_status = PlayingStatus.PLAYING
    mock_wiim_device.volume = 60  # 0.6
    mock_wiim_device.current_media = WiimMediaMetadata(title="New Song")
    mock_wiim_device.available = True  # type: ignore[misc]

    entity._device = mock_wiim_device
    entity.entity_id = "media_player.test_device"
    entity._attr_group_members = ["media_player.test_device", "media_player.follower1"]

    with (
        patch.object(entity, "schedule_update_ha_state", new=MagicMock()),
        patch.object(entity, "async_write_ha_state", new=MagicMock()),
        patch.object(
            entity.hass.data[DATA_WIIM].controller,
            "get_group_snapshot",
            new=MagicMock(
                return_value=MagicMock(
                    role=WiimGroupRole.LEADER,
                    member_udns=(mock_wiim_device.udn,),
                )
            ),
        ),
    ):
        entity._update_ha_state_from_sdk_cache()

        assert entity.state == MediaPlayerState.PLAYING
        assert entity.volume_level == 0.6
        assert entity.media_title == "New Song"


async def test_media_player_update_ha_state_from_sdk_cache_unavailable(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test unavailable devices clear state and write HA state."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass
    entity._device = mock_wiim_device
    entity._attr_media_title = "Old"
    entity._attr_source = "Old Source"
    entity._transport_capabilities = WiimTransportCapabilities(can_next=True)
    mock_wiim_device.available = False  # type: ignore[misc]

    with patch.object(entity, "async_write_ha_state", new=MagicMock()) as mock_write:
        entity._update_ha_state_from_sdk_cache()

    assert entity.state is None
    assert entity.media_title is None
    assert entity.source is None
    assert entity._transport_capabilities is None
    mock_write.assert_called_once()


async def test_media_player_update_ha_state_from_sdk_cache_follower_uses_leader_device(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test follower metadata is pulled from the leader device cache."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.follower"
    entity._device = mock_wiim_device

    leader_device = MagicMock(spec=WiimDevice)
    leader_device.udn = "uuid:leader-1234"
    leader_device.playing_status = PlayingStatus.PLAYING
    leader_device.play_mode = "Network"
    leader_device.loop_state = mock_wiim_device.loop_state
    leader_device.current_media = WiimMediaMetadata(
        title="Leader Song",
        artist="Leader Artist",
        album="Leader Album",
        image_url="http://leader/image.jpg",
        uri="http://leader/track.flac",
        duration=180,
        position=42,
    )

    mock_controller = MagicMock()
    mock_controller.get_group_snapshot.return_value = MagicMock(
        role=WiimGroupRole.FOLLOWER,
        leader_udn=leader_device.udn,
        member_udns=(leader_device.udn, mock_wiim_device.udn),
    )
    mock_controller.get_device.return_value = leader_device
    _set_wiim_data(
        mock_hass,
        controller=mock_controller,
        entity_id_to_udn_map={"media_player.follower": mock_wiim_device.udn},
    )

    with patch.object(
        entity, "_async_schedule_update_supported_features", new=MagicMock()
    ):
        entity._update_ha_state_from_sdk_cache(
            write_state=False,
            update_supported_features=False,
        )

    assert entity.state == MediaPlayerState.PLAYING
    assert entity.media_title == "Leader Song"
    assert entity.media_artist == "Leader Artist"
    assert entity.media_album_name == "Leader Album"
    assert entity.media_image_url == "http://leader/image.jpg"
    assert entity.media_content_id == "http://leader/track.flac"
    assert entity.media_duration == 180
    assert entity.media_position == 42


async def test_media_player_async_added_to_hass_refreshes_supported_features(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_hass: HomeAssistant,
) -> None:
    """Test entity setup refreshes supported features before initial state write."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.test_device"
    _set_wiim_data(mock_hass)

    with (
        patch(
            "homeassistant.helpers.entity.Entity.async_added_to_hass",
            new=AsyncMock(),
        ),
        patch.object(
            entity, "_from_device_update_supported_features", new_callable=AsyncMock
        ) as mock_refresh_supported_features,
        patch.object(
            entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
        ) as mock_update_state,
        patch.object(
            entity, "async_write_ha_state", new=MagicMock()
        ) as mock_write_state,
    ):
        await entity.async_added_to_hass()

    assert (
        entity._device.general_event_callback
        == entity._handle_sdk_general_device_update
    )
    assert (
        entity._device.av_transport_event_callback
        == entity._handle_sdk_av_transport_event
    )
    assert (
        entity._device.rendering_control_event_callback
        == entity._handle_sdk_refresh_event
    )
    assert entity._device.play_queue_event_callback == entity._handle_sdk_refresh_event
    assert (
        entity._wiim_data.entity_id_to_udn_map[entity.entity_id] == entity._device.udn
    )
    mock_refresh_supported_features.assert_awaited_once_with(write_state=False)
    mock_update_state.assert_called_once_with(
        write_state=False, update_supported_features=False
    )
    mock_write_state.assert_not_called()


async def test_media_player_update_supported_features_adds_detected_features(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test supported features are added when the device reports support."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.test_device"
    entity._platform_state = EntityPlatformState.ADDED
    _set_wiim_data(mock_hass)

    mock_wiim_device.supports_http_api = True
    mock_wiim_device.async_get_transport_capabilities.return_value = (
        WiimTransportCapabilities(
            can_next=True,
            can_previous=False,
            can_repeat=True,
            can_shuffle=False,
        )
    )

    expected_features = (
        SUPPORT_WIIM_BASE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.REPEAT_SET
    )

    with patch.object(entity, "async_write_ha_state", new=MagicMock()) as mock_write:
        await entity._from_device_update_supported_features()

    assert entity.supported_features == expected_features
    mock_write.assert_called_once()


async def test_media_player_update_supported_features_can_skip_state_write(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test supported features can be refreshed without writing entity state."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.test_device"
    entity._platform_state = EntityPlatformState.ADDED
    _set_wiim_data(mock_hass)

    mock_wiim_device.supports_http_api = True
    mock_wiim_device.async_get_transport_capabilities.return_value = (
        WiimTransportCapabilities(can_next=True, can_previous=False)
    )

    expected_features = SUPPORT_WIIM_BASE | MediaPlayerEntityFeature.NEXT_TRACK

    with patch.object(entity, "async_write_ha_state", new=MagicMock()) as mock_write:
        await entity._from_device_update_supported_features(write_state=False)

    assert entity.supported_features == expected_features
    mock_write.assert_not_called()


async def test_media_player_update_supported_features_follower_uses_leader_device(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test follower supported features are read from the leader device."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.follower"
    _set_wiim_data(mock_hass)

    leader_device = MagicMock(spec=WiimDevice)
    leader_device.udn = "uuid:leader-1234"
    leader_device.async_get_transport_capabilities = AsyncMock(
        return_value=WiimTransportCapabilities(
            can_next=True,
            can_previous=False,
            can_repeat=True,
            can_shuffle=False,
        )
    )

    entity._wiim_data.controller.get_group_snapshot.return_value = MagicMock(
        role=WiimGroupRole.FOLLOWER,
        leader_udn=leader_device.udn,
        member_udns=(leader_device.udn, mock_wiim_device.udn),
    )
    entity._wiim_data.controller.get_device.return_value = leader_device

    await entity._from_device_update_supported_features(write_state=False)

    assert entity.supported_features == (
        SUPPORT_WIIM_BASE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.REPEAT_SET
    )
    leader_device.async_get_transport_capabilities.assert_awaited_once()


async def test_media_player_update_supported_features_skips_write_when_unchanged(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test failed capability refresh does not write state when features stay unchanged."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.test_device"
    entity._platform_state = EntityPlatformState.ADDED
    _set_wiim_data(mock_hass)

    mock_wiim_device.async_get_transport_capabilities.side_effect = (
        WiimRequestException("boom")
    )

    with patch.object(entity, "async_write_ha_state", new=MagicMock()) as mock_write:
        await entity._from_device_update_supported_features()

    assert entity.supported_features == SUPPORT_WIIM_BASE
    mock_write.assert_not_called()


async def test_media_player_update_supported_features_follower_clears_on_none(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test follower clears cached capabilities when leader returns none."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.follower"
    _set_wiim_data(mock_hass)
    entity._transport_capabilities = WiimTransportCapabilities(can_next=True)

    leader_device = MagicMock(spec=WiimDevice)
    leader_device.udn = "uuid:leader-5678"

    entity._wiim_data.controller.get_group_snapshot.return_value = MagicMock(
        role=WiimGroupRole.FOLLOWER,
        leader_udn=leader_device.udn,
        member_udns=(leader_device.udn, mock_wiim_device.udn),
    )
    entity._wiim_data.controller.get_device.return_value = leader_device

    with patch.object(
        entity,
        "_async_get_transport_capabilities_for_device",
        new=AsyncMock(return_value=None),
    ):
        await entity._from_device_update_supported_features(write_state=False)

    assert entity._transport_capabilities is None


async def test_media_player_schedule_update_skips_when_in_flight(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
) -> None:
    """Test scheduling skips when an update is already in flight."""
    entity = mock_wiim_media_player_entity
    entity._supported_features_update_in_flight = True

    with patch.object(
        entity._entry,
        "async_create_background_task",
        new=MagicMock(),
    ) as mock_create_task:
        entity._async_schedule_update_supported_features()

    mock_create_task.assert_not_called()


async def test_media_player_registry_update_syncs_entity_id(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_hass: HomeAssistant,
) -> None:
    """Test registry updates sync the UDN map for renamed entities."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    _set_wiim_data(
        mock_hass,
        entity_id_to_udn_map={"media_player.old": entity._device.udn},
    )

    event = Event(
        "entity_registry_updated",
        {
            "action": "update",
            "old_entity_id": "media_player.old",
            "entity_id": "media_player.new",
        },
    )

    with patch.object(Entity, "_async_registry_updated", new=MagicMock()):
        entity._async_registry_updated(event)

    assert "media_player.old" not in entity._wiim_data.entity_id_to_udn_map
    assert (
        entity._wiim_data.entity_id_to_udn_map["media_player.new"] == entity._device.udn
    )


async def test_media_player_async_will_remove_clears_callbacks(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_hass: HomeAssistant,
) -> None:
    """Test removal clears callbacks and unregisters entity mapping."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    _set_wiim_data(
        mock_hass,
        entity_id_to_udn_map={entity.entity_id: entity._device.udn},
    )
    entity._device.general_event_callback = entity._handle_sdk_general_device_update
    entity._device.av_transport_event_callback = entity._handle_sdk_av_transport_event
    entity._device.rendering_control_event_callback = entity._handle_sdk_refresh_event
    entity._device.play_queue_event_callback = entity._handle_sdk_refresh_event

    with patch.object(
        Entity, "async_will_remove_from_hass", new=AsyncMock()
    ) as mock_super:
        await entity.async_will_remove_from_hass()

    assert entity._device.general_event_callback is None
    assert entity._device.av_transport_event_callback is None
    assert entity._device.rendering_control_event_callback is None
    assert entity._device.play_queue_event_callback is None
    assert entity.entity_id not in entity._wiim_data.entity_id_to_udn_map
    mock_super.assert_awaited_once()


async def test_media_player_async_handle_critical_error_marks_unavailable(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test critical errors mark device unavailable and refresh state."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity._device = mock_wiim_device
    mock_wiim_device.available = True  # type: ignore[misc]
    mock_wiim_device.set_available = MagicMock()
    _set_wiim_data(mock_hass)
    entity._wiim_data.controller.async_update_all_multiroom_status = AsyncMock()

    with patch.object(
        entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
    ) as mock_update_state:
        await entity._async_handle_critical_error(WiimException("boom"))

    mock_wiim_device.set_available.assert_called_once_with(False)
    mock_update_state.assert_called_once()
    entity._wiim_data.controller.async_update_all_multiroom_status.assert_awaited_once()


async def test_media_player_async_handle_critical_error_already_unavailable(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test critical errors still trigger multiroom refresh when offline."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity._device = mock_wiim_device
    mock_wiim_device.available = False  # type: ignore[misc]
    mock_wiim_device.set_available = MagicMock()
    _set_wiim_data(mock_hass)
    entity._wiim_data.controller.async_update_all_multiroom_status = AsyncMock()

    with patch.object(
        entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
    ) as mock_update_state:
        await entity._async_handle_critical_error(WiimException("offline"))

    mock_wiim_device.set_available.assert_not_called()
    mock_update_state.assert_not_called()
    entity._wiim_data.controller.async_update_all_multiroom_status.assert_awaited_once()


async def test_media_player_handle_invalid_transport_state_event(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test invalid transport state events only log and still refresh state."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.test_device"
    entity._device = mock_wiim_device
    mock_wiim_device.event_data = {"TransportState": "not-a-valid-state"}
    original_status = mock_wiim_device.playing_status

    with (
        patch.object(
            entity._entry,
            "async_create_background_task",
            new=MagicMock(),
        ) as mock_create_task,
        patch.object(
            entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
        ) as mock_update_state,
    ):
        entity._handle_sdk_av_transport_event(MagicMock(), [])

    assert mock_wiim_device.playing_status == original_status
    mock_create_task.assert_not_called()
    mock_update_state.assert_called_once()


async def test_media_player_handle_stopped_transport_state_event(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test STOPPED transport state clears media position metadata."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.test_device"
    entity._device = mock_wiim_device
    mock_wiim_device.event_data = {"TransportState": PlayingStatus.STOPPED.value}
    mock_wiim_device.current_position = 10
    mock_wiim_device.current_track_duration = 120
    entity._attr_media_position = 10
    entity._attr_media_duration = 120
    entity._attr_media_position_updated_at = object()

    with patch.object(
        entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
    ) as mock_update_state:
        entity._handle_sdk_av_transport_event(MagicMock(), [])

    assert mock_wiim_device.current_position == 0
    assert mock_wiim_device.current_track_duration == 0
    assert entity._attr_media_position is None
    assert entity._attr_media_duration is None
    assert entity._attr_media_position_updated_at is None
    mock_update_state.assert_called_once()


async def test_media_player_handle_playing_transport_state_event(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test valid playing transport state events schedule a position refresh."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.test_device"
    entity._device = mock_wiim_device
    mock_wiim_device.event_data = {"TransportState": PlayingStatus.PLAYING.value}

    sync_task = object()

    with (
        patch.object(
            mock_wiim_device,
            "sync_device_duration_and_position",
            new=MagicMock(return_value=sync_task),
        ),
        patch.object(
            entity._entry,
            "async_create_background_task",
            new=MagicMock(),
        ) as mock_create_task,
        patch.object(
            entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
        ) as mock_update_state,
    ):
        entity._handle_sdk_av_transport_event(MagicMock(), [])

    assert mock_wiim_device.playing_status is PlayingStatus.PLAYING
    mock_create_task.assert_called_once()
    assert mock_create_task.call_args.args[1] is sync_task
    mock_update_state.assert_called_once()


async def test_media_player_handle_refresh_event(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
) -> None:
    """Test refresh events only trigger a state update."""
    entity = mock_wiim_media_player_entity

    with patch.object(
        entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
    ) as mock_update_state:
        entity._handle_sdk_refresh_event(MagicMock(), [])

    mock_update_state.assert_called_once()


async def test_media_player_general_update_unavailable(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test general update handles device going unavailable."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity._device = mock_wiim_device
    mock_wiim_device.available = False  # type: ignore[misc]

    with (
        patch.object(
            entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
        ) as mock_update_state,
        patch.object(
            entity._entry,
            "async_create_background_task",
            new=MagicMock(side_effect=lambda _hass, coro, name=None: coro.close()),
        ) as mock_create_task,
    ):
        entity._handle_sdk_general_device_update(mock_wiim_device)

    mock_update_state.assert_called_once()
    mock_create_task.assert_called_once()


async def test_media_player_general_update_http_api_refreshes(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test general update schedules a subscription refresh for HTTP devices."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity._device = mock_wiim_device
    mock_wiim_device.available = True  # type: ignore[misc]
    mock_wiim_device.supports_http_api = True
    mock_wiim_device.ensure_subscriptions = AsyncMock()
    _set_wiim_data(mock_hass)

    with (
        patch.object(
            entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
        ) as mock_update_state,
        patch.object(
            entity._entry,
            "async_create_background_task",
            new=MagicMock(),
        ) as mock_create_task,
    ):
        entity._handle_sdk_general_device_update(mock_wiim_device)

        coro = mock_create_task.call_args.args[1]
        await coro

        mock_wiim_device.ensure_subscriptions.assert_awaited_once()
        mock_update_state.assert_called_once()


async def test_media_player_general_update_non_http_api_updates_immediately(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test general update refreshes immediately for non-HTTP devices."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity._device = mock_wiim_device
    mock_wiim_device.available = True  # type: ignore[misc]
    mock_wiim_device.supports_http_api = False

    with (
        patch.object(
            entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
        ) as mock_update_state,
        patch.object(
            entity._entry,
            "async_create_background_task",
            new=MagicMock(),
        ) as mock_create_task,
    ):
        entity._handle_sdk_general_device_update(mock_wiim_device)

    mock_update_state.assert_called_once()
    mock_create_task.assert_not_called()


async def test_media_player_async_get_transport_capabilities_runtime_error(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
) -> None:
    """Test runtime errors in capability fetch return None."""
    entity = mock_wiim_media_player_entity
    mock_wiim_device.async_get_transport_capabilities.side_effect = RuntimeError("boom")

    result = await entity._async_get_transport_capabilities_for_device(mock_wiim_device)

    assert result is None


async def test_media_player_play(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player play service."""
    entity = mock_wiim_media_player_entity

    _set_wiim_data(mock_hass)

    entity.hass = mock_hass

    with patch.object(
        mock_wiim_device, "async_play", new_callable=AsyncMock
    ) as mock_play:
        await entity.async_media_play()
        mock_play.assert_awaited_once()


async def test_media_player_play_redirects_follower_to_leader(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test play redirects to the group leader for followers."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.follower"

    leader_device = MagicMock(spec=WiimDevice)
    leader_device.udn = "uuid:leader-1234"

    mock_controller = MagicMock()
    mock_controller.get_group_snapshot.return_value = MagicMock(
        role=WiimGroupRole.FOLLOWER,
        command_target_udn="uuid:leader-1234",
    )
    mock_controller.get_device.return_value = leader_device
    _set_wiim_data(
        mock_hass,
        controller=mock_controller,
    )

    with (
        patch.object(
            entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
        ) as mock_update_state,
        patch.object(
            mock_wiim_device, "async_play", new_callable=AsyncMock
        ) as mock_play,
        patch.object(
            leader_device, "async_play", new_callable=AsyncMock
        ) as mock_leader_play,
    ):
        await entity.async_media_play()

    mock_update_state.assert_called_once()
    mock_play.assert_not_awaited()
    mock_leader_play.assert_awaited_once()


async def test_media_player_pause(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player pause service."""
    entity = mock_wiim_media_player_entity

    _set_wiim_data(mock_hass)

    entity.hass = mock_hass
    entity._device = mock_wiim_device

    with patch.object(
        mock_wiim_device, "async_pause", new_callable=AsyncMock
    ) as mock_pause:
        await entity.async_media_pause()
        mock_pause.assert_awaited_once()


async def test_media_player_pause_wraps_runtime_error(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test runtime errors are wrapped as HomeAssistantError."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass

    mock_wiim_device.async_pause = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch.object(
            entity, "_async_handle_critical_error", new_callable=AsyncMock
        ) as mock_handle,
        patch.object(
            entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
        ) as mock_update_state,
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_media_pause()

    mock_handle.assert_not_awaited()
    mock_update_state.assert_not_called()


async def test_media_player_stop(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player stop service."""
    entity = mock_wiim_media_player_entity

    _set_wiim_data(mock_hass)

    entity.hass = mock_hass
    with patch.object(
        mock_wiim_device, "async_stop", new_callable=AsyncMock
    ) as mock_stop:
        await entity.async_media_stop()
        mock_stop.assert_awaited_once()


async def test_media_player_set_volume(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player set volume service."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass
    with patch.object(
        mock_wiim_device, "async_set_volume", new_callable=AsyncMock
    ) as mock_set_volume:
        await entity.async_set_volume_level(0.75)
        mock_set_volume.assert_awaited_once_with(75)


async def test_media_player_set_volume_handles_sdk_error(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test SDK errors are wrapped and trigger critical handling."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass

    mock_wiim_device.async_set_volume = AsyncMock(
        side_effect=WiimRequestException("boom")
    )

    with (
        patch.object(
            entity, "_async_handle_critical_error", new_callable=AsyncMock
        ) as mock_handle,
        patch.object(
            entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
        ) as mock_update_state,
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_set_volume_level(0.5)

    mock_handle.assert_awaited_once()
    mock_update_state.assert_not_called()


async def test_media_player_mute_volume(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player mute volume service."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass
    with patch.object(
        mock_wiim_device, "async_set_mute", new_callable=AsyncMock
    ) as mock_set_mute:
        await entity.async_mute_volume(True)
        mock_set_mute.assert_awaited_once_with(True)


async def test_media_player_play_media_url(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player play media service with a URL."""
    entity = mock_wiim_media_player_entity
    mock_wiim_device.supports_http_api = True
    entity._device = mock_wiim_device
    entity.hass = mock_hass
    _set_wiim_data(mock_hass)

    with patch.object(
        mock_wiim_device, "play_preset", new_callable=AsyncMock
    ) as mock_http_cmd_ok:
        await entity.async_play_media(MediaType.MUSIC, "1")
        mock_http_cmd_ok.assert_awaited_once_with(1)


async def test_media_player_select_source(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player select source service."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass

    with patch.object(
        mock_wiim_device, "async_set_play_mode", new_callable=AsyncMock
    ) as mock_play_mode:
        await entity.async_select_source("Bluetooth")
        mock_play_mode.assert_awaited_once()


async def test_media_player_seek(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player seek service."""
    entity = mock_wiim_media_player_entity

    _set_wiim_data(mock_hass)

    entity.hass = mock_hass

    with patch.object(
        mock_wiim_device, "async_seek", new_callable=AsyncMock
    ) as mock_seek:
        await entity.async_media_seek(60)
        mock_seek.assert_awaited_once_with(60)


async def test_media_player_seek_redirects_follower_to_leader(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test seek redirects to the group leader for followers."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.follower"

    leader_device = MagicMock(spec=WiimDevice)
    leader_device.udn = "uuid:leader-1234"

    mock_controller = MagicMock()
    mock_controller.get_group_snapshot.return_value = MagicMock(
        role=WiimGroupRole.FOLLOWER,
        command_target_udn="uuid:leader-1234",
    )
    mock_controller.get_device.return_value = leader_device
    _set_wiim_data(
        mock_hass,
        controller=mock_controller,
    )

    with (
        patch.object(
            entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
        ) as mock_update_state,
        patch.object(
            mock_wiim_device, "async_seek", new_callable=AsyncMock
        ) as mock_seek,
        patch.object(
            leader_device, "async_seek", new_callable=AsyncMock
        ) as mock_leader_seek,
    ):
        await entity.async_media_seek(60)

    mock_update_state.assert_called_once()
    mock_seek.assert_not_awaited()
    mock_leader_seek.assert_awaited_once_with(60)


async def test_media_player_next(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player next track service."""
    entity = mock_wiim_media_player_entity

    _set_wiim_data(mock_hass)

    entity.hass = mock_hass

    with patch.object(
        mock_wiim_device, "async_next", new_callable=AsyncMock
    ) as mock_next:
        await entity.async_media_next_track()
        mock_next.assert_awaited_once()


async def test_media_player_previous(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player previous track service."""
    entity = mock_wiim_media_player_entity

    _set_wiim_data(mock_hass)

    entity.hass = mock_hass

    with patch.object(
        mock_wiim_device, "async_previous", new_callable=AsyncMock
    ) as mock_previous:
        await entity.async_media_previous_track()
        mock_previous.assert_awaited_once()


async def test_media_player_set_repeat_mode(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media player set repeat mode service."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
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


async def test_media_player_set_shuffle_uses_default_repeat(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test shuffle uses OFF repeat when repeat is unset."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass
    entity._attr_repeat = None

    with patch.object(
        mock_wiim_device, "async_set_loop_mode", new_callable=AsyncMock
    ) as mock_loop_mode:
        await entity.async_set_shuffle(True)

    mock_wiim_device.build_loop_mode.assert_called_once_with(WiimRepeatMode.OFF, True)
    mock_loop_mode.assert_awaited_once()


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
    _set_wiim_data(
        mock_hass,
        controller=mock_controller,
        entity_id_to_udn_map={"media_player.other_wiim_device": "uuid:target-456"},
    )
    mock_hass.data["media_source"] = {}
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
    ) as mock_browse_media:
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
    mock_browse_media.assert_not_awaited()


async def test_media_player_browse_media_root_includes_media_sources(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test root browse includes media sources when HTTP API is available."""
    entity = mock_wiim_media_player_entity
    mock_wiim_device.supports_http_api = True
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass

    media_source_child = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="media-source://audio",
        media_content_type=MediaType.MUSIC,
        title="Media Source",
        can_play=False,
        can_expand=True,
        children=[],
    )

    media_sources_item = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="media-source://root",
        media_content_type=MediaType.MUSIC,
        title="Root",
        can_play=False,
        can_expand=True,
        children=[media_source_child],
    )

    with patch(
        "homeassistant.components.media_source.async_browse_media",
        AsyncMock(return_value=media_sources_item),
    ):
        browse_result = await entity.async_browse_media(MEDIA_CONTENT_ID_ROOT)

    assert browse_result.children is not None
    assert len(browse_result.children) == 3
    assert browse_result.children[2].title == "Media Source"


async def test_media_player_browse_media_favorites(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity, mock_wiim_device: WiimDevice
) -> None:
    """Test Browse favorites (presets)."""
    entity = mock_wiim_media_player_entity
    with patch.object(
        mock_wiim_device, "async_get_presets", new_callable=AsyncMock
    ) as mock_fav:
        mock_fav.return_value = (
            WiimPreset(1, "Preset 1", "http://image1.jpg"),
            WiimPreset(2, "Preset 2", "http://image2.jpg"),
        )

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
        assert child_item.media_content_id == "1"
        assert child_item.media_content_type == MediaType.MUSIC
        assert child_item.title == "Preset 1"
        assert child_item.can_play is True
        assert child_item.can_expand is False
        assert child_item.thumbnail == "http://image1.jpg"


async def test_media_player_browse_media_source_requires_http_api(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
) -> None:
    """Test media source browsing is gated when HTTP API is unavailable."""
    entity = mock_wiim_media_player_entity

    with (
        patch(
            "homeassistant.components.media_source.is_media_source_id",
            return_value=True,
        ),
        pytest.raises(BrowseError, match="Media sources are not supported"),
    ):
        await entity.async_browse_media(media_content_id="media-source://some-source")


async def test_media_player_browse_media_source_with_http_api(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test media source browse is delegated when HTTP API is available."""
    entity = mock_wiim_media_player_entity
    mock_wiim_device.supports_http_api = True
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass

    media_source_item = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="media-source://root",
        media_content_type=MediaType.MUSIC,
        title="Media Source Root",
        can_play=False,
        can_expand=True,
        children=[],
    )

    with (
        patch(
            "homeassistant.components.media_source.is_media_source_id",
            return_value=True,
        ),
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(return_value=media_source_item),
        ),
    ):
        result = await entity.async_browse_media(media_content_id="media-source://root")

    assert result is media_source_item


async def test_media_player_browse_media_playlists_queue(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity, mock_wiim_device: WiimDevice
) -> None:
    """Test browsing media playlists queues for the Wiim media player entity."""
    entity = mock_wiim_media_player_entity

    with patch.object(
        mock_wiim_device, "async_get_queue_snapshot", new_callable=AsyncMock
    ) as mock_get_queue_snapshot:
        mock_get_queue_snapshot.return_value = WiimQueueSnapshot(
            items=(
                WiimQueueItem(1, "Song A", "Artist A"),
                WiimQueueItem(2, "Song B", "Artist B"),
            ),
            source_name="SPOTIFY",
            play_medium="SONGLIST-NETWORK",
            track_source="SPOTIFY",
            is_active=True,
        )

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
        mock_get_queue_snapshot.assert_awaited_once()


async def test_media_player_browse_media_queue_inactive(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity, mock_wiim_device: WiimDevice
) -> None:
    """Test browsing queue when inactive returns empty children."""
    entity = mock_wiim_media_player_entity

    with patch.object(
        mock_wiim_device, "async_get_queue_snapshot", new_callable=AsyncMock
    ) as mock_get_queue_snapshot:
        mock_get_queue_snapshot.return_value = WiimQueueSnapshot(
            items=(),
            source_name="",
            play_medium="",
            track_source="",
            is_active=False,
        )

        browse_result = await entity.async_browse_media(
            MediaType.PLAYLIST, MEDIA_CONTENT_ID_PLAYLISTS
        )

    assert browse_result.children == []
    mock_get_queue_snapshot.assert_awaited_once()


async def test_async_play_media_source(hass: HomeAssistant) -> None:
    """Test async_play_media for a media-source URL."""
    mock_device = AsyncMock()
    mock_device.supports_http_api = True
    mock_device.available = True
    mock_device.volume = 50
    mock_device.is_muted = False
    mock_device.supported_input_modes = ()
    mock_device.playing_status = None
    mock_device.play_mode = None
    mock_device.loop_state = MagicMock(repeat=WiimRepeatMode.OFF, shuffle=False)
    mock_device.current_media = None

    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.runtime_data = mock_device
    mock_entry.async_create_background_task.side_effect = lambda hass, coro, name=None: (
        hass.async_create_task(coro)
    )

    entity = WiimMediaPlayerEntity(mock_device, mock_entry)
    entity.hass = hass
    entity.entity_id = "media_player.test_device"
    entity._attr_state = MediaPlayerState.IDLE
    _set_wiim_data(hass)

    media_id = "media-source://some-song"
    mock_play_item = MagicMock()
    mock_play_item.url = "http://resolved-url/song.mp3"

    with (
        patch(
            "homeassistant.components.media_source.is_media_source_id",
            return_value=True,
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            new=AsyncMock(return_value=mock_play_item),
        ),
    ):
        await entity.async_play_media(media_type=MediaType.MUSIC, media_id=media_id)

    expected_url = async_process_play_media_url(hass, mock_play_item.url)
    mock_device.play_url.assert_awaited_once_with(expected_url)

    assert entity._attr_state == MediaPlayerState.PLAYING


async def test_async_play_media_source_requires_http_api(
    hass: HomeAssistant,
    mock_wiim_device: WiimDevice,
) -> None:
    """Test media-source playback is gated when HTTP API is unavailable."""
    mock_wiim_device.supports_http_api = False

    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.runtime_data = mock_wiim_device
    mock_entry.async_create_background_task.side_effect = lambda hass, coro, name=None: (
        hass.async_create_task(coro)
    )

    entity = WiimMediaPlayerEntity(mock_wiim_device, mock_entry)
    entity.hass = hass
    entity.entity_id = "media_player.test_device"
    _set_wiim_data(hass)

    with (
        patch(
            "homeassistant.components.media_source.is_media_source_id",
            return_value=True,
        ),
        pytest.raises(ServiceValidationError, match="Media sources are not supported"),
    ):
        await entity.async_play_media(
            media_type=MediaType.MUSIC,
            media_id="media-source://some-song",
        )


async def test_async_play_media_invalid_preset_id(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_hass: HomeAssistant,
) -> None:
    """Test invalid preset ID raises validation error."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass

    with pytest.raises(ServiceValidationError, match="Invalid preset ID"):
        await entity.async_play_media(MediaType.MUSIC, "not-a-number")


async def test_async_play_media_track_invalid_index(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_hass: HomeAssistant,
) -> None:
    """Test invalid track index raises validation error."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass

    with pytest.raises(ServiceValidationError, match="Expected a valid track index"):
        await entity.async_play_media(MediaType.TRACK, "track-1")


async def test_async_play_media_track_valid_index(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test valid track index plays queue and updates attributes."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass
    mock_wiim_device.async_play_queue_with_index = AsyncMock()

    with patch.object(entity, "_update_ha_state_from_sdk_cache", new=MagicMock()):
        await entity.async_play_media(MediaType.TRACK, "2")

    mock_wiim_device.async_play_queue_with_index.assert_awaited_once_with(2)
    assert entity._attr_media_content_id == "wiim_track_2"
    assert entity._attr_media_content_type == MediaType.TRACK
    assert entity._attr_state == MediaPlayerState.PLAYING


async def test_async_play_media_unsupported_type(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_hass: HomeAssistant,
) -> None:
    """Test unsupported media type raises validation error."""
    entity = mock_wiim_media_player_entity
    _set_wiim_data(mock_hass)
    entity.hass = mock_hass

    with pytest.raises(ServiceValidationError, match="Unsupported media type"):
        await entity.async_play_media("video", "1")


async def test_media_player_play_media_routes_follower_to_leader(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
    mock_wiim_device: WiimDevice,
    mock_hass: HomeAssistant,
) -> None:
    """Test play_media routes follower commands through the group leader."""
    entity = mock_wiim_media_player_entity
    entity.hass = mock_hass
    entity.entity_id = "media_player.follower"

    leader_device = MagicMock(spec=WiimDevice)
    leader_device.udn = "uuid:leader-1234"
    leader_device.play_preset = AsyncMock()

    mock_controller = MagicMock()
    mock_controller.get_group_snapshot.return_value = MagicMock(
        role=WiimGroupRole.FOLLOWER,
        command_target_udn=leader_device.udn,
    )
    mock_controller.get_device.return_value = leader_device
    _set_wiim_data(mock_hass, controller=mock_controller)

    with patch.object(
        entity, "_update_ha_state_from_sdk_cache", new=MagicMock()
    ) as mock_update_state:
        await entity.async_play_media(MediaType.MUSIC, "1")

    mock_update_state.assert_called_once()
    leader_device.play_preset.assert_awaited_once_with(1)
    mock_wiim_device.play_preset.assert_not_awaited()


async def test_media_player_browse_media_invalid_path(
    mock_wiim_media_player_entity: WiimMediaPlayerEntity,
) -> None:
    """Test invalid browse path raises BrowseError."""
    entity = mock_wiim_media_player_entity

    with pytest.raises(BrowseError, match="Invalid browse path"):
        await entity.async_browse_media(MediaType.MUSIC, "invalid_path")
