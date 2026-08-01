"""Tests for the Proxmox VE sensor platform."""

from unittest.mock import MagicMock, patch

from proxmoxer.core import ResourceException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.proxmoxve.const import DOMAIN, ProxmoxAgentState
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import PVEVMUSER_PERMISSIONS, setup_integration

from tests.common import (
    MockConfigEntry,
    async_load_json_array_fixture,
    snapshot_platform,
)


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass,
            entity_registry,
            snapshot,
            mock_config_entry.entry_id,
        )


async def test_storage_missing_used_fraction(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test storage usage percentage sensor when used_fraction is missing."""
    storage_data = await async_load_json_array_fixture(
        hass, "nodes/storage.json", "proxmoxve"
    )
    # Remove used_fraction from all storage entries
    storage_without_fraction = [
        {key: value for key, value in storage.items() if key != "used_fraction"}
        for storage in storage_data
    ]
    mock_proxmox_client._node_mock.storage.get.return_value = storage_without_fraction

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.storage_local_storage_usage_percentage")
    assert state.state == STATE_UNKNOWN


async def test_sensors_according_to_permissions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensors are not created when not allowed."""
    mock_proxmox_client.access.permissions.get.return_value = PVEVMUSER_PERMISSIONS

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert "sensor.pve1_status" in {e.entity_id for e in entries}
    assert "sensor.pve1_cpu" not in {e.entity_id for e in entries}


@pytest.mark.parametrize(
    ("vmid", "expected_state", "agent_side_effect"),
    [
        (100, ProxmoxAgentState.ACTIVE, None),
        (100, ProxmoxAgentState.INACTIVE, ResourceException("500", "error", "content")),
        (101, ProxmoxAgentState.UNKNOWN, None),
    ],
)
async def test_agent_state(
    hass: HomeAssistant,
    mock_proxmox_client,
    mock_config_entry,
    vmid,
    expected_state,
    agent_side_effect,
) -> None:
    """Normal conditions for guest agent state."""
    vm_data = await async_load_json_array_fixture(hass, "nodes/qemu.json", DOMAIN)

    node_mock = mock_proxmox_client.nodes.return_value
    node_mock.qemu.get.return_value = vm_data

    vm_mock = MagicMock()
    vm_mock.agent.ping.post.side_effect = agent_side_effect
    vm_mock.agent.ping.post.return_value = {"result": {}}

    node_mock.qemu.side_effect = lambda *args: vm_mock if args else node_mock.qemu

    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    assert coordinator.data["pve1"].vms[vmid]["guest_agent"] == expected_state
