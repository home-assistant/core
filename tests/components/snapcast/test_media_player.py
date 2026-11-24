"""Test the snapcast media player implementation."""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from snapcast.control.client import Snapclient
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    MediaPlayerEntityFeature,
    MediaPlayerService,
    MediaPlayerServiceArgument,
    MediaPlayerState,
)
from homeassistant.components.snapcast.const import DOMAIN
from homeassistant.components.snapcast.services import (
    SnapcastService,
    SnapcastServiceArgument,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration


async def test_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test basic state information."""

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("domain", "service", "service_data", "method", "args"),
    [
        (
            MEDIA_PLAYER_DOMAIN,
            MediaPlayerService.VOLUME_SET,
            {MediaPlayerServiceArgument.VOLUME_LEVEL: 0.37},
            "set_volume",
            (37,),
        ),
        (
            MEDIA_PLAYER_DOMAIN,
            MediaPlayerService.VOLUME_MUTE,
            {MediaPlayerServiceArgument.IS_VOLUME_MUTED: True},
            "set_muted",
            (True,),
        ),
        (
            DOMAIN,
            SnapcastService.SET_LATENCY,
            {SnapcastServiceArgument.LATENCY: 25},
            "set_latency",
            (25,),
        ),
        (DOMAIN, SnapcastService.RESTORE, {}, "restore", ()),
    ],
    ids=["volume", "mute", "latency", "restore"],
)
async def test_client_identity_survives_reconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_client_1: AsyncMock,
    mock_client_2: AsyncMock,
    mock_group_1: AsyncMock,
    entity_registry: er.EntityRegistry,
    domain: str,
    service: str,
    service_data: dict[str, float | bool | int],
    method: str,
    args: tuple[int | bool, ...],
) -> None:
    """Test a reconnect cannot rebind an entity to another physical client."""
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    entity_id = "media_player.test_client_1_snapcast_client"
    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    original_unique_id = registry_entry.unique_id
    original_callback = mock_client_1.set_callback.call_args.args[0]
    assert original_callback is not None

    mock_create_server.clients = [mock_client_2]
    mock_config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.unique_id == original_unique_id
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    mock_client_1.set_callback.assert_called_with(None)

    replacement_client = AsyncMock(spec=Snapclient)
    replacement_client.identifier = mock_client_1.identifier
    replacement_client.friendly_name = mock_client_1.friendly_name
    replacement_client.version = mock_client_1.version
    replacement_client.connected = True
    replacement_client.name = mock_client_1.name
    replacement_client.latency = mock_client_1.latency
    replacement_client.muted = False
    replacement_client.volume = 77
    replacement_client.group = mock_group_1

    mock_create_server.clients = [replacement_client, mock_client_2]
    mock_config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    replacement_client.set_callback.assert_called_once()
    replacement_callback = replacement_client.set_callback.call_args.args[0]
    assert replacement_callback is not None
    assert replacement_callback.__self__ is original_callback.__self__

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == MediaPlayerState.PLAYING

    await hass.services.async_call(
        domain,
        service,
        {TargetKey.ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )

    getattr(replacement_client, method).assert_awaited_once_with(*args)
    getattr(mock_client_1, method).assert_not_called()
    getattr(mock_client_2, method).assert_not_called()

    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.unique_id == original_unique_id


async def test_snapshot_during_disconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_client_1: AsyncMock,
    mock_client_2: AsyncMock,
) -> None:
    """A snapshot can only be taken while the targeted client is present."""
    await setup_integration(hass, mock_config_entry)
    target = {TargetKey.ENTITY_ID: "media_player.test_client_1_snapcast_client"}
    await hass.services.async_call(
        DOMAIN, SnapcastService.SNAPSHOT, target, blocking=True
    )
    mock_client_1.snapshot.assert_called_once_with()

    # The client disappears between HA's availability check and the snapshot.
    with (
        patch.object(
            mock_create_server,
            "client",
            side_effect=[mock_client_1, KeyError(mock_client_1.identifier)],
        ),
        pytest.raises(ServiceValidationError, match="not currently available"),
    ):
        await hass.services.async_call(
            DOMAIN, SnapcastService.SNAPSHOT, target, blocking=True
        )

    mock_client_1.snapshot.assert_called_once_with()
    mock_client_2.snapshot.assert_not_called()


@pytest.mark.parametrize(
    ("members"),
    [
        ["media_player.test_client_2_snapcast_client"],
        [
            "media_player.test_client_1_snapcast_client",
            "media_player.test_client_2_snapcast_client",
        ],
    ],
)
async def test_join(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_group_1: AsyncMock,
    mock_client_2: AsyncMock,
    members: list[str],
) -> None:
    """Test grouping of media players through the join service."""

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.JOIN,
        {
            TargetKey.ENTITY_ID: "media_player.test_client_1_snapcast_client",
            MediaPlayerServiceArgument.GROUP_MEMBERS: members,
        },
        blocking=True,
    )
    mock_group_1.add_client.assert_awaited_once_with(mock_client_2.identifier)


async def test_unjoin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_client_1: AsyncMock,
    mock_group_1: AsyncMock,
) -> None:
    """Test the unjoin service removes the client from the group."""

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.UNJOIN,
        {
            TargetKey.ENTITY_ID: "media_player.test_client_1_snapcast_client",
        },
        blocking=True,
    )

    mock_group_1.remove_client.assert_awaited_once_with(mock_client_1.identifier)


async def test_join_non_snapcast_client(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_group_1: AsyncMock,
) -> None:
    """Test join throws when trying to add a non-Snapcast client."""

    # Create a dummy media player entity
    entity_registry.async_get_or_create(
        MEDIA_PLAYER_DOMAIN,
        "dummy",
        "media_player_1",
    )
    await hass.async_block_till_done()

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(
        ServiceValidationError,
        match=r"Entity .*? is not a Snapcast client device.",
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            MediaPlayerService.JOIN,
            {
                TargetKey.ENTITY_ID: "media_player.test_client_1_snapcast_client",
                MediaPlayerServiceArgument.GROUP_MEMBERS: [
                    "media_player.dummy_media_player_1"
                ],
            },
            blocking=True,
        )

    # Ensure that the group did not attempt to add a non-Snapcast client
    mock_group_1.add_client.assert_not_awaited()


async def test_join_different_server(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_group_1: AsyncMock,
) -> None:
    """Test join throws when joining a Snapcast client from another server."""

    # Create a dummy Snapcast client with a different unique_id prefix
    entity_registry.async_get_or_create(
        MEDIA_PLAYER_DOMAIN,
        "snapcast",
        "snapcast_client_server2_client2",
    )
    await hass.async_block_till_done()

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(
        ServiceValidationError,
        match=r"Entity .*? does not belong to the same Snapcast server.",
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            MediaPlayerService.JOIN,
            {
                TargetKey.ENTITY_ID: "media_player.test_client_1_snapcast_client",
                MediaPlayerServiceArgument.GROUP_MEMBERS: [
                    "media_player.snapcast_snapcast_client_server2_client2"
                ],
            },
            blocking=True,
        )

    # Ensure that the group did not attempt to add the client
    mock_group_1.add_client.assert_not_awaited()


async def test_join_client_key_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_group_1: AsyncMock,
) -> None:
    """Test join service throws an exception when a key error is thrown."""

    # add_client will throw a KeyError if the client identifier
    # is not found on the server
    mock_group_1.add_client = AsyncMock(side_effect=KeyError())

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            MediaPlayerService.JOIN,
            {
                TargetKey.ENTITY_ID: "media_player.test_client_1_snapcast_client",
                MediaPlayerServiceArgument.GROUP_MEMBERS: [
                    "media_player.test_client_2_snapcast_client"
                ],
            },
            blocking=True,
        )

    mock_group_1.add_client.assert_awaited_once()


async def test_join_client_identifier_underscore(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_group_1: AsyncMock,
    mock_client_2: AsyncMock,
) -> None:
    """Test join service properly handles client identifiers with underscores."""

    mock_client_2.identifier = "test_client_underscore"

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.JOIN,
        {
            TargetKey.ENTITY_ID: "media_player.test_client_1_snapcast_client",
            MediaPlayerServiceArgument.GROUP_MEMBERS: [
                "media_player.test_client_2_snapcast_client"
            ],
        },
        blocking=True,
    )

    mock_group_1.add_client.assert_awaited_once_with("test_client_underscore")


async def test_stream_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_group_2: AsyncMock,
) -> None:
    """Test server.stream call KeyError."""
    mock_create_server.streams = []

    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("media_player.test_client_2_snapcast_client")
    assert "media_position" not in state.attributes
    assert "metadata" not in state.attributes


async def test_state_stream_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_group_1: AsyncMock,
) -> None:
    """Test state returns OFF when stream is not found."""

    type(mock_group_1).stream_status = PropertyMock(
        side_effect=KeyError("Stream not found")
    )

    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("media_player.test_client_1_snapcast_client")
    assert state.state == "off"


async def test_attributes_group_is_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_client_1: AsyncMock,
) -> None:
    """Test exceptions are not thrown when a client has no group."""
    # Force nonexistent group
    mock_client_1.group = None

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("media_player.test_client_1_snapcast_client")

    # Assert accessing state and attributes doesn't throw
    assert state.state == MediaPlayerState.IDLE

    assert state.attributes["group_members"] is None
    assert "source" not in state.attributes
    assert "source_list" not in state.attributes
    assert "metadata" not in state.attributes
    assert "media_position" not in state.attributes


async def test_select_source_group_is_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_client_1: AsyncMock,
    mock_group_1: AsyncMock,
) -> None:
    """Test select source throws a validation error when client has no group."""
    # Force nonexistent group
    mock_client_1.group = None

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            MediaPlayerService.SELECT_SOURCE,
            {
                TargetKey.ENTITY_ID: "media_player.test_client_1_snapcast_client",
                MediaPlayerServiceArgument.SOURCE: "fake_source",
            },
            blocking=True,
        )
    mock_group_1.set_stream.assert_not_awaited()


async def test_join_group_is_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_group_1: AsyncMock,
    mock_client_1: AsyncMock,
) -> None:
    """Test join action throws a service validation error when a client has no group."""
    # Force nonexistent group
    mock_client_1.group = None

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            MediaPlayerService.JOIN,
            {
                TargetKey.ENTITY_ID: "media_player.test_client_1_snapcast_client",
                MediaPlayerServiceArgument.GROUP_MEMBERS: [
                    "media_player.test_client_2_snapcast_client"
                ],
            },
            blocking=True,
        )
    mock_group_1.add_client.assert_not_awaited()


async def test_unjoin_group_is_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_client_1: AsyncMock,
    mock_group_1: AsyncMock,
) -> None:
    """Test unjoin throws a validation error when client has no group."""
    # Force nonexistent group
    mock_client_1.group = None

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            MediaPlayerService.UNJOIN,
            {
                TargetKey.ENTITY_ID: "media_player.test_client_1_snapcast_client",
            },
            blocking=True,
        )
    mock_group_1.remove_client.assert_not_awaited()


@pytest.mark.parametrize(
    ("service", "command"),
    [
        (SERVICE_MEDIA_PLAY, "play"),
        (SERVICE_MEDIA_PAUSE, "pause"),
        (SERVICE_MEDIA_PLAY_PAUSE, "playPause"),
        (SERVICE_MEDIA_STOP, "stop"),
        (SERVICE_MEDIA_NEXT_TRACK, "next"),
        (SERVICE_MEDIA_PREVIOUS_TRACK, "previous"),
    ],
)
async def test_stream_transport_controls(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_stream_1: AsyncMock,
    service: str,
    command: str,
) -> None:
    """Test transport controls are forwarded to the active Snapcast stream."""
    mock_stream_1.properties = {
        "canControl": True,
        "canPlay": True,
        "canPause": True,
        "canGoNext": True,
        "canGoPrevious": True,
        "canSeek": False,
        "playbackStatus": "playing",
    }

    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: "media_player.test_client_1_snapcast_client",
        },
        blocking=True,
    )

    mock_create_server.stream_control.assert_awaited_once_with(
        mock_stream_1.identifier,
        command,
        {},
    )


async def test_stream_transport_supported_features(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_stream_1: AsyncMock,
) -> None:
    """Test transport capabilities come from the active Snapcast stream."""
    mock_stream_1.properties = {
        "canControl": True,
        "canPlay": True,
        "canPause": True,
        "canGoNext": True,
        "canGoPrevious": False,
        "canSeek": False,
        "playbackStatus": "playing",
    }

    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("media_player.test_client_1_snapcast_client")
    assert state is not None
    features = MediaPlayerEntityFeature(state.attributes["supported_features"])

    assert features & MediaPlayerEntityFeature.PLAY
    assert features & MediaPlayerEntityFeature.PAUSE
    assert features & MediaPlayerEntityFeature.NEXT_TRACK
    assert not features & MediaPlayerEntityFeature.PREVIOUS_TRACK
    assert features & MediaPlayerEntityFeature.STOP
    assert not features & MediaPlayerEntityFeature.SEEK


async def test_stream_transport_not_supported_without_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_stream_1: AsyncMock,
) -> None:
    """Test transport features are hidden for an uncontrollable stream."""
    mock_stream_1.properties = {
        "canControl": False,
        "canPlay": True,
        "canPause": True,
        "canGoNext": True,
        "canGoPrevious": True,
        "playbackStatus": "playing",
    }

    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("media_player.test_client_1_snapcast_client")
    assert state is not None
    features = MediaPlayerEntityFeature(state.attributes["supported_features"])

    assert not features & MediaPlayerEntityFeature.PLAY
    assert not features & MediaPlayerEntityFeature.PAUSE
    assert not features & MediaPlayerEntityFeature.NEXT_TRACK
    assert not features & MediaPlayerEntityFeature.PREVIOUS_TRACK
    assert not features & MediaPlayerEntityFeature.STOP


async def test_stream_playback_status_paused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
    mock_stream_1: AsyncMock,
) -> None:
    """Test playback status from the stream is reflected by the client."""
    mock_stream_1.properties = {
        "canControl": True,
        "canPlay": True,
        "canPause": True,
        "playbackStatus": "paused",
    }

    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("media_player.test_client_1_snapcast_client")
    assert state is not None
    assert state.state == MediaPlayerState.PAUSED
