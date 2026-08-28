"""Tests for VM/container live migration between Proxmox nodes."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.proxmoxve.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


def _full_node(node_name: str) -> dict[str, Any]:
    """Return a complete Proxmox node response."""
    return {
        "id": f"node/{node_name}",
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
    "vmid": "200",
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
    "vmid": "201",
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


def _set_cluster_data(
    mock_proxmox_client: MagicMock,
    resources: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]],
    node_order: tuple[str, ...] | None = None,
) -> dict[str, MagicMock]:
    """Configure the mocked API responses for each node."""
    node_mocks: dict[str, MagicMock] = {}
    for node_name, (vms, containers) in resources.items():
        node_mock = MagicMock()
        node_mock.qemu.get.return_value = vms
        node_mock.lxc.get.return_value = containers
        node_mock.storage.get.return_value = []
        node_mock.tasks.get.return_value = []
        node_mocks[node_name] = node_mock

    mock_proxmox_client._nodes_mock.side_effect = node_mocks.__getitem__
    mock_proxmox_client.nodes.get.return_value = [
        _full_node(node_name) for node_name in node_order or tuple(resources)
    ]
    return node_mocks


def _get_entity_id(
    entity_registry: er.EntityRegistry, entry_id: str, unique_id_suffix: str
) -> str:
    """Look up an entity ID by unique ID suffix."""
    for entry in er.async_entries_for_config_entry(entity_registry, entry_id):
        if entry.unique_id.endswith(unique_id_suffix):
            return entry.entity_id
    raise AssertionError(f"No entity found with unique ID ending in {unique_id_suffix}")


def _state_value(hass: HomeAssistant, entity_id: str) -> str:
    """Return an entity state after proving that it exists."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


def _resource_entity_identity(
    entity_registry: er.EntityRegistry, entry_id: str, resource_id: int
) -> dict[str, tuple[str, str]]:
    """Return the public registry identity of every entity for a resource."""
    unique_id_prefix = f"{entry_id}_{resource_id}_"
    return {
        entry.unique_id: (entry.entity_id, entry.id)
        for entry in er.async_entries_for_config_entry(entity_registry, entry_id)
        if entry.unique_id.startswith(unique_id_prefix)
    }


def _get_child_device(
    device_registry: dr.DeviceRegistry,
    entry_id: str,
    resource_kind: str,
    resource_id: int,
) -> dr.DeviceEntry:
    """Return a VM/container device from the registry."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_{resource_kind}_{resource_id}"), entry_id
    )
    assert device is not None
    return device


def _matching_device_count(
    device_registry: dr.DeviceRegistry,
    entry_id: str,
    resource_kind: str,
    resource_id: int,
) -> int:
    """Count registry devices matching one Proxmox resource identifier."""
    identifier = (DOMAIN, f"{entry_id}_{resource_kind}_{resource_id}")
    return sum(
        identifier in device.identifiers
        for device in dr.async_entries_for_config_entry(device_registry, entry_id)
    )


@pytest.mark.parametrize(
    ("resource_kind", "resource_id", "endpoint"),
    [("vm", 100, "qemu"), ("container", 200, "lxc")],
)
async def test_migration_source_dual_target(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    resource_kind: str,
    resource_id: int,
    endpoint: str,
) -> None:
    """Test migration uses public polling and keeps registry identity stable."""
    initial_vms = [_VM_100, _VM_101]
    initial_containers = [_CT_200, _CT_201]
    _set_cluster_data(
        mock_proxmox_client,
        {"pve1": (initial_vms, initial_containers)},
    )

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR, Platform.BUTTON],
    ):
        await setup_integration(hass, mock_config_entry)

    entry_id = mock_config_entry.entry_id
    status_entity_id = _get_entity_id(
        entity_registry, entry_id, f"{resource_id}_status"
    )
    button_entity_id = _get_entity_id(
        entity_registry, entry_id, f"{resource_id}_restart"
    )
    assert _state_value(hass, status_entity_id) == STATE_ON

    initial_entity_identity = _resource_entity_identity(
        entity_registry, entry_id, resource_id
    )
    assert initial_entity_identity
    source_node_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_node_node/pve1"), entry_id
    )
    assert source_node_device is not None
    child_device = _get_child_device(
        device_registry, entry_id, resource_kind, resource_id
    )
    child_device_id = child_device.id
    assert child_device.via_device_id == source_node_device.id

    target_resource = {
        **(_VM_100 if resource_kind == "vm" else _CT_200),
        "status": "stopped",
    }
    target_vms = [target_resource] if resource_kind == "vm" else []
    target_containers = [target_resource] if resource_kind == "container" else []
    _set_cluster_data(
        mock_proxmox_client,
        {
            "pve1": (initial_vms, initial_containers),
            "pve2": (target_vms, target_containers),
        },
    )
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    target_node_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_node_node/pve2"), entry_id
    )
    assert target_node_device is not None
    assert _state_value(hass, status_entity_id) == STATE_ON
    assert (
        _resource_entity_identity(entity_registry, entry_id, resource_id)
        == initial_entity_identity
    )
    assert (
        _get_child_device(device_registry, entry_id, resource_kind, resource_id).id
        == child_device_id
    )
    assert (
        _get_child_device(
            device_registry, entry_id, resource_kind, resource_id
        ).via_device_id
        == source_node_device.id
    )

    source_vms = [_VM_101] if resource_kind == "vm" else initial_vms
    source_containers = (
        [_CT_201] if resource_kind == "container" else initial_containers
    )
    target_node_mocks = _set_cluster_data(
        mock_proxmox_client,
        {
            "pve1": (source_vms, source_containers),
            "pve2": (target_vms, target_containers),
        },
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _state_value(hass, status_entity_id) == STATE_OFF
    assert (
        _resource_entity_identity(entity_registry, entry_id, resource_id)
        == initial_entity_identity
    )
    assert (
        _get_child_device(device_registry, entry_id, resource_kind, resource_id).id
        == child_device_id
    )
    assert (
        _get_child_device(
            device_registry, entry_id, resource_kind, resource_id
        ).via_device_id
        == target_node_device.id
    )
    assert (
        _matching_device_count(device_registry, entry_id, resource_kind, resource_id)
        == 1
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: button_entity_id},
        blocking=True,
    )

    target_endpoint = getattr(target_node_mocks["pve2"], endpoint)
    target_endpoint.assert_called_once_with(resource_id)
    target_endpoint.return_value.status.reboot.post.assert_called_once_with()


@pytest.mark.parametrize("node_order", [("pve1", "pve2"), ("pve2", "pve1")])
async def test_new_dual_node_resources_choose_node_deterministically(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    node_order: tuple[str, str],
) -> None:
    """Test new dual-node resources choose the same observable parent device."""
    _set_cluster_data(
        mock_proxmox_client,
        {"pve1": ([_VM_100, _VM_101], [_CT_200, _CT_201])},
    )

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    new_vm_source = {**_VM_100, "vmid": 999, "name": "vm-new"}
    new_vm_target = {**new_vm_source, "status": "stopped"}
    new_container_source = {**_CT_200, "vmid": 888, "name": "ct-new"}
    new_container_target = {**new_container_source, "status": "stopped"}
    _set_cluster_data(
        mock_proxmox_client,
        {
            "pve1": (
                [_VM_100, _VM_101, new_vm_source],
                [_CT_200, _CT_201, new_container_source],
            ),
            "pve2": ([new_vm_target], [new_container_target]),
        },
        node_order,
    )

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entry_id = mock_config_entry.entry_id
    source_node_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_node_node/pve1"), entry_id
    )
    assert source_node_device is not None

    for resource_kind, resource_id in (("vm", 999), ("container", 888)):
        status_entity_id = _get_entity_id(
            entity_registry, entry_id, f"{resource_id}_status"
        )
        assert _state_value(hass, status_entity_id) == STATE_ON
        child_device = _get_child_device(
            device_registry, entry_id, resource_kind, resource_id
        )
        assert child_device.via_device_id == source_node_device.id
        assert (
            _matching_device_count(
                device_registry, entry_id, resource_kind, resource_id
            )
            == 1
        )
