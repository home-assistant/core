"""Tests for the Proxmox VE sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.proxmoxve.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

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
        hass, "nodes/storage.json", DOMAIN
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

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "1234_pve1_local_storage_used_percentage"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_sensors_missing_data(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors when data is missing from Proxmox API."""

    # Mock node data with missing fields
    all_nodes = await async_load_json_array_fixture(hass, "nodes/nodes.json", DOMAIN)
    node1 = next((n for n in all_nodes if n["node"] == "pve1"), None)
    assert node1 is not None

    # Remove some fields from node
    node1_incomplete = {
        k: v
        for k, v in node1.items()
        if k not in ["cpu", "mem", "maxmem", "disk", "maxdisk", "uptime"]
    }
    mock_proxmox_client.nodes.get.return_value = [node1_incomplete]

    # Mock storage with missing used_fraction and other fields
    storage_data = await async_load_json_array_fixture(
        hass, "nodes/storage.json", DOMAIN
    )
    storage_incomplete = [
        {
            k: v
            for k, v in s.items()
            if k not in ["used_fraction", "used", "total", "avail"]
        }
        for s in storage_data
    ]
    # Add a zero-capacity storage pool
    storage_incomplete.append(
        {
            "storage": "zero_pool",
            "total": 0,
            "used": 0,
            "avail": 0,
            "active": 1,
            "enabled": 1,
            "type": "nfs",
        }
    )
    mock_proxmox_client._node_mock.storage.get.return_value = storage_incomplete

    # Malformed backup (missing starttime/endtime but entry exists)
    mock_proxmox_client._node_mock.tasks.get.return_value = [
        {"upid": "UPID:pve1:00000000:00000000:00000000:vzdump:100:root@pam:"}
    ]

    # Mock VM/Container with missing fields
    qemu_data = await async_load_json_array_fixture(hass, "nodes/qemu.json", DOMAIN)
    qemu_incomplete = [
        {
            k: v
            for k, v in vm.items()
            if k
            not in [
                "cpu",
                "mem",
                "maxmem",
                "disk",
                "maxdisk",
                "uptime",
                "netin",
                "netout",
            ]
        }
        for vm in qemu_data
    ]
    mock_proxmox_client._node_mock.qemu.get.return_value = qemu_incomplete

    lxc_data = await async_load_json_array_fixture(hass, "nodes/lxc.json", DOMAIN)
    lxc_incomplete = [
        {
            k: v
            for k, v in ct.items()
            if k
            not in [
                "cpu",
                "mem",
                "maxmem",
                "disk",
                "maxdisk",
                "uptime",
                "netin",
                "netout",
            ]
        }
        for ct in lxc_data
    ]
    mock_proxmox_client._node_mock.lxc.get.return_value = lxc_incomplete

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    entity_registry = er.async_get(hass)

    # Check entity creation logic
    # Node sensors (Node CPU usage) - SHOULD exist (transient data)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "1234_node/pve1_node_cpu"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Backup sensors (Node backup last backup) - SHOULD exist
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "1234_node/pve1_node_backup_last_backup"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Storage sensors (Local storage usage percentage) - SHOULD exist, reports unknown
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "1234_pve1_local_storage_used_percentage"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Zero pool storage (Zero pool used storage) - SHOULD exist, reports 0
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "1234_pve1_zero_pool_storage_used"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 0.0

    # Zero pool usage percentage - SHOULD exist, reports unknown (no used_fraction)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "1234_pve1_zero_pool_storage_used_percentage"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # VM sensors (VM Web memory percentage) - SHOULD exist
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "1234_100_vm_memory_percentage"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Container sensors (CT Nginx memory percentage) - SHOULD exist
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "1234_200_container_memory_percentage"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
