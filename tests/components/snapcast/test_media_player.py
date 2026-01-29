"""Test the snapcast media player implementation."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_JOIN,
    SERVICE_UNJOIN,
    SERVICE_VOLUME_SET,
)
from homeassistant.components.snapcast.const import ATTR_MASTER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

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


async def test_join_exception(
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

    with pytest.raises(ServiceValidationError):
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


async def test_legacy_join_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
) -> None:
    """Test the legacy grouping services create issues when used."""

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    # Call the legacy join service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_client_2_snapcast_client",
            ATTR_MASTER: "media_player.test_client_1_snapcast_client",
        },
        blocking=True,
    )

    # Verify the issue is created
    issue = issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id="deprecated_grouping_actions",
    )
    assert issue is not None

    # Clear existing issue
    issue_registry.async_delete(
        domain=DOMAIN,
        issue_id="deprecated_grouping_actions",
    )

    # Call legacy unjoin service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_UNJOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_client_2_snapcast_client",
        },
        blocking=True,
    )

    # Verify the issue is created again
    issue = issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id="deprecated_grouping_actions",
    )
    assert issue is not None


async def test_deprecated_group_entity_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_create_server: AsyncMock,
) -> None:
    """Test the legacy group entities create issues when used."""

    # Setup and verify the integration is loaded
    with patch("secrets.token_hex", return_value="mock_token"):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    # Call a servuce that uses a group entity
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        service_data={
            ATTR_ENTITY_ID: "media_player.test_group_1_snapcast_group",
            ATTR_MEDIA_VOLUME_LEVEL: 0.5,
        },
        blocking=True,
    )

    # Verify the issue is created
    issue = issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id="deprecated_group_entities",
    )
    assert issue is not None
