"""Tests for the Proxmox VE update platform."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import AUDIT_PERMISSIONS, MERGED_PERMISSIONS, setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import WebSocketGenerator

ENTITY_ID = "update.pve1"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    # Ensure Sys.Modify permissions to ensure update status can be determined
    mock_proxmox_client.access.permissions.get.return_value = MERGED_PERMISSIONS
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_update_unavailable(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that updates are unavailable with only auditor permissions."""
    mock_proxmox_client.access.permissions.get.return_value = AUDIT_PERMISSIONS

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


async def test_update_up_to_date(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that updates are up to date when no updates are pending."""
    mock_proxmox_client.access.permissions.get.return_value = MERGED_PERMISSIONS
    mock_proxmox_client.nodes.return_value.apt.update.get.return_value = []

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get("latest_version") == "9.1.6"
    assert state.state == STATE_OFF


async def test_update_release_notes(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that updates release notes are correctly set."""
    mock_proxmox_client.access.permissions.get.return_value = MERGED_PERMISSIONS

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {"id": 1, "type": "update/release_notes", "entity_id": ENTITY_ID}
    )
    result = await ws_client.receive_json()
    assert "5 package" in result["result"]
