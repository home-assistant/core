"""Tests for the Proxmox VE update platform."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import AUDIT_PERMISSIONS, MERGED_PERMISSIONS, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


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


async def test_update_available(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that buttons are raising accordingly for Auditor permissions."""
    mock_proxmox_client.access.permissions.get.return_value = AUDIT_PERMISSIONS

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("update.pve1")
    assert state is not None
    assert state.state == "off"
