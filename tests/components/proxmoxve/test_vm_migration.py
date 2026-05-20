"""Tests for VM/container live migration between Proxmox nodes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.proxmoxve.coordinator import ProxmoxNodeData
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


def _full_node(node_name: str, node_id: str) -> dict:
    """Return a complete node dict suitable for ProxmoxNodeData.node."""
    return {
        "id": node_id,
        "node": node_name,
        "status": "online",
        "level": "",
        "type": "node",
        "maxmem": 34359738368,
        "mem": 12884901888,
        "maxcpu": 8,
        "cpu": 0.12,
        "uptime": 86400,
        "maxdisk": 500000000000,
        "disk": 100000000000,
        "ssl_fingerprint": "AA:BB:CC:...:DD",
    }


_VM_100 = {
    "vmid": 100,
    "name": "vm-web",
    "status": "running",
    "maxmem": 2147483648,
    "cpus": 2,
    "mem": 1073741824,
    "cpu": 0.15,
    "maxdisk": 34359738368,
    "disk": 1234567890,
    "uptime": 86400,
}

_VM_101 = {
    "vmid": 101,
    "name": "vm-db",
    "status": "stopped",
    "maxmem": 2147483648,
    "cpus": 2,
    "mem": 1073741824,
    "cpu": 0.15,
    "maxdisk": 34359738368,
    "disk": 1234567890,
    "uptime": 86400,
}

_CT_200 = {
    "vmid": 200,
    "name": "ct-nginx",
    "status": "running",
    "maxmem": 1073741824,
    "cpus": 1,
    "mem": 536870912,
    "cpu": 0.05,
    "maxdisk": 21474836480,
    "disk": 1125899906,
    "uptime": 43200,
}

_CT_201 = {
    "vmid": 201,
    "name": "ct-backup",
    "status": "stopped",
    "maxmem": 1073741824,
    "cpus": 1,
    "mem": 536870912,
    "cpu": 0.05,
    "maxdisk": 21474836480,
    "disk": 1125899906,
    "uptime": 43200,
}


def _get_entity_id(
    entity_registry: er.EntityRegistry, entry_id: str, unique_id_suffix: str
) -> str:
    """Look up entity_id by unique_id suffix, independent of entity naming."""
    for entry in er.async_entries_for_config_entry(entity_registry, entry_id):
        if entry.unique_id.endswith(unique_id_suffix):
            return entry.entity_id
    raise AssertionError(f"No entity found with unique_id ending in {unique_id_suffix}")


async def test_vm_migration_updates_entity(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a VM migrated to another node keeps entities working."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    entity_id = _get_entity_id(
        entity_registry, mock_config_entry.entry_id, "100_status"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    # VM 100 moves from pve1 to pve2
    new_data = {
        "pve1": ProxmoxNodeData(
            node=_full_node("pve1", "node/pve1"),
            vms={101: _VM_101},
            containers={200: _CT_200, 201: _CT_201},
        ),
        "pve2": ProxmoxNodeData(
            node=_full_node("pve2", "node/pve2"),
            vms={100: {**_VM_100, "cpu": 0.30, "uptime": 172800}},
            containers={},
        ),
    }

    coordinator = mock_config_entry.runtime_data
    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON


async def test_container_migration_updates_entity(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a container migrated to another node keeps entities working."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    entity_id = _get_entity_id(
        entity_registry, mock_config_entry.entry_id, "200_status"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    # Container 200 moves from pve1 to pve2
    new_data = {
        "pve1": ProxmoxNodeData(
            node=_full_node("pve1", "node/pve1"),
            vms={100: _VM_100, 101: _VM_101},
            containers={201: _CT_201},
        ),
        "pve2": ProxmoxNodeData(
            node=_full_node("pve2", "node/pve2"),
            vms={},
            containers={200: {**_CT_200, "cpu": 0.10, "uptime": 86400}},
        ),
    }

    coordinator = mock_config_entry.runtime_data
    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON


async def test_dual_node_during_migration_prefers_source(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a VM visible on two nodes during migration stays on the source."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.vmid_node_map[100] == "pve1"

    # Mid-migration: VM 100 appears on both pve1 (source) and pve2 (target)
    mid_migration_data = {
        "pve1": ProxmoxNodeData(
            node=_full_node("pve1", "node/pve1"),
            vms={100: _VM_100, 101: _VM_101},
            containers={200: _CT_200, 201: _CT_201},
        ),
        "pve2": ProxmoxNodeData(
            node=_full_node("pve2", "node/pve2"),
            vms={100: {**_VM_100, "cpu": 0.30}},
            containers={},
        ),
    }
    coordinator.async_set_updated_data(mid_migration_data)
    await hass.async_block_till_done()

    # Source node (pve1) should be preferred
    assert coordinator.vmid_node_map[100] == "pve1"

    entity_id = _get_entity_id(
        entity_registry, mock_config_entry.entry_id, "100_status"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON


async def test_dual_node_does_not_duplicate_entities(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a VMID visible on two nodes results in a single entity."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data

    # Mid-migration snapshot: VM 100 and container 200 appear on both nodes.
    dual_node_data = {
        "pve1": ProxmoxNodeData(
            node=_full_node("pve1", "node/pve1"),
            vms={100: _VM_100, 101: _VM_101},
            containers={200: _CT_200, 201: _CT_201},
        ),
        "pve2": ProxmoxNodeData(
            node=_full_node("pve2", "node/pve2"),
            vms={100: {**_VM_100, "cpu": 0.30}},
            containers={200: {**_CT_200, "cpu": 0.10}},
        ),
    }
    coordinator.async_set_updated_data(dual_node_data)
    await hass.async_block_till_done()

    # Exactly one entity per VMID/CTID, regardless of dual-node visibility.
    vm_status_entries = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id.endswith("100_status")
    ]
    assert len(vm_status_entries) == 1

    ct_status_entries = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id.endswith("200_status")
    ]
    assert len(ct_status_entries) == 1


async def test_id_node_map_is_deterministic_on_first_resolution(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a new VMID seen on multiple nodes resolves deterministically."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data

    # A brand new VMID (999) appears on two nodes at once, with no prior
    # entry in vmid_node_map. The chosen node must not depend on dict
    # iteration order.
    new_vm = {**_VM_100, "vmid": 999, "name": "vm-new"}
    new_ct = {**_CT_200, "vmid": 888, "name": "ct-new"}

    data_order_a = {
        "pve2": ProxmoxNodeData(
            node=_full_node("pve2", "node/pve2"),
            vms={999: new_vm},
            containers={888: new_ct},
        ),
        "pve1": ProxmoxNodeData(
            node=_full_node("pve1", "node/pve1"),
            vms={100: _VM_100, 999: new_vm},
            containers={200: _CT_200, 888: new_ct},
        ),
    }
    coordinator.vmid_node_map = {}
    coordinator.ctid_node_map = {}
    coordinator._build_id_node_maps(data_order_a)
    choice_a_vm = coordinator.vmid_node_map[999]
    choice_a_ct = coordinator.ctid_node_map[888]

    data_order_b = {
        "pve1": ProxmoxNodeData(
            node=_full_node("pve1", "node/pve1"),
            vms={100: _VM_100, 999: new_vm},
            containers={200: _CT_200, 888: new_ct},
        ),
        "pve2": ProxmoxNodeData(
            node=_full_node("pve2", "node/pve2"),
            vms={999: new_vm},
            containers={888: new_ct},
        ),
    }
    coordinator.vmid_node_map = {}
    coordinator.ctid_node_map = {}
    coordinator._build_id_node_maps(data_order_b)
    choice_b_vm = coordinator.vmid_node_map[999]
    choice_b_ct = coordinator.ctid_node_map[888]

    assert choice_a_vm == choice_b_vm == "pve1"
    assert choice_a_ct == choice_b_ct == "pve1"
