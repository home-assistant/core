"""Test the snapcast media player implementation."""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_JOIN,
    SERVICE_SELECT_SOURCE,
    SERVICE_UNJOIN,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


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
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_client_1_snapcast_client",
            ATTR_GROUP_MEMBERS: members,
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
        SERVICE_UNJOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_client_1_snapcast_client",
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
    """Test join service throws an exception when trying to add a non-Snapcast client."""

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
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_client_1_snapcast_client",
                ATTR_GROUP_MEMBERS: ["media_player.dummy_media_player_1"],
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
    """Test join service throws an exception when trying to join a Snapcast client from another server."""

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
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_client_1_snapcast_client",
                ATTR_GROUP_MEMBERS: [
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

    # add_client will throw a KeyError if the client identifier is not found on the server
    mock_group_1.add_client = AsyncMock(side_effect=KeyError())

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_client_1_snapcast_client",
                ATTR_GROUP_MEMBERS: ["media_player.test_client_2_snapcast_client"],
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
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_client_1_snapcast_client",
            ATTR_GROUP_MEMBERS: ["media_player.test_client_2_snapcast_client"],
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
    """Test the select source action throws a service validation error when a client has no group."""
    # Force nonexistent group
    mock_client_1.group = None

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {
                ATTR_ENTITY_ID: "media_player.test_client_1_snapcast_client",
                ATTR_INPUT_SOURCE: "fake_source",
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
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_client_1_snapcast_client",
                ATTR_GROUP_MEMBERS: ["media_player.test_client_2_snapcast_client"],
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
    """Test the unjoin action throws a service validation error when a client has no group."""
    # Force nonexistent group
    mock_client_1.group = None

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_UNJOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_client_1_snapcast_client",
            },
            blocking=True,
        )
    mock_group_1.remove_client.assert_not_awaited()
