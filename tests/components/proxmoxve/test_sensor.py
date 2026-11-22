"""Tests for the Proxmox VE sensor platform."""

from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.proxmoxve.coordinator import DEFAULT_UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import PVEVMUSER_PERMISSIONS, setup_integration


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.freeze_time("2026-05-03T12:00:00+00:00")
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


@pytest.mark.parametrize(
    ("cluster_resources", "expected_percentage"),
    [
        pytest.param(
            [{"type": "qemu", "vmid": 100, "mem": 536870912}],
            "25.0",
            id="guest_memory",
        ),
        pytest.param([], "50.0", id="not_in_cluster_resources"),
    ],
)
async def test_vm_memory_source(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    cluster_resources: list[dict[str, Any]],
    expected_percentage: str,
) -> None:
    """Test VM memory comes from cluster resources, falling back to the node list."""
    mock_proxmox_client.cluster.resources.get.return_value = cluster_resources

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.vm_web_memory_usage_percentage")
    assert state.state == expected_percentage


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


async def test_sensors_for_offline_node(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that node sensors except status are unavailable."""
    mock_proxmox_client.nodes.get.return_value = mock_proxmox_client._all_nodes

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.pve3_status")
    assert state.state == "offline"

    state = hass.states.get("sensor.pve3_disk_usage")
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.pve4_status")
    assert state.state == "unknown"

    state = hass.states.get("sensor.pve4_disk_usage")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("endpoint", "vmid", "entity_id"),
    [
        pytest.param("qemu", 100, "sensor.vm_web_uptime", id="vm"),
        pytest.param("lxc", "200", "sensor.ct_nginx_uptime", id="container"),
    ],
)
@pytest.mark.parametrize(
    ("status", "uptime"),
    [
        pytest.param("stopped", 0, id="stopped"),
        pytest.param("stopped", 3600, id="stopped_with_uptime"),
        pytest.param("running", 0, id="running_without_uptime"),
        pytest.param("running", None, id="running_uptime_none"),
    ],
)
async def test_guest_uptime_unknown(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    endpoint: str,
    vmid: int | str,
    entity_id: str,
    status: str,
    uptime: int | None,
) -> None:
    """Test the uptime is unknown and stays unchanged for a guest that is not up."""
    guests = getattr(mock_proxmox_client._node_mock, endpoint).get.return_value
    guest = next(guest for guest in guests if guest["vmid"] == vmid)
    guest["status"] = status
    guest["uptime"] = uptime

    with patch("homeassistant.components.proxmoxve.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
    last_changed = state.last_changed

    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.last_changed == last_changed
