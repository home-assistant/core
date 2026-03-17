"""Tests for VM/container live migration between Proxmox nodes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.proxmoxve.coordinator import ProxmoxNodeData
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


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
            node={
                "id": "node/pve1",
                "node": "pve1",
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
                "ssl_fingerprint": "5C:D2:AB:...:D9",
            },
            vms={
                101: {
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
                },
            },
            containers={
                200: {
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
                },
                201: {
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
                },
            },
        ),
        "pve2": ProxmoxNodeData(
            node={
                "id": "node/pve2",
                "node": "pve2",
                "status": "online",
                "level": "",
                "type": "node",
                "maxmem": 34359738368,
                "mem": 16106127360,
                "maxcpu": 8,
                "cpu": 0.25,
                "uptime": 72000,
                "maxdisk": 500000000000,
                "disk": 120000000000,
                "ssl_fingerprint": "7A:E1:DF:...:AC",
            },
            vms={
                100: {
                    "vmid": 100,
                    "name": "vm-web",
                    "status": "running",
                    "maxmem": 2147483648,
                    "cpus": 2,
                    "mem": 1073741824,
                    "cpu": 0.30,
                    "maxdisk": 34359738368,
                    "disk": 1234567890,
                    "uptime": 172800,
                },
            },
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
            node={
                "id": "node/pve1",
                "node": "pve1",
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
                "ssl_fingerprint": "5C:D2:AB:...:D9",
            },
            vms={
                100: {
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
                },
                101: {
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
                },
            },
            containers={
                201: {
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
                },
            },
        ),
        "pve2": ProxmoxNodeData(
            node={
                "id": "node/pve2",
                "node": "pve2",
                "status": "online",
                "level": "",
                "type": "node",
                "maxmem": 34359738368,
                "mem": 16106127360,
                "maxcpu": 8,
                "cpu": 0.25,
                "uptime": 72000,
                "maxdisk": 500000000000,
                "disk": 120000000000,
                "ssl_fingerprint": "7A:E1:DF:...:AC",
            },
            vms={},
            containers={
                200: {
                    "vmid": 200,
                    "name": "ct-nginx",
                    "status": "running",
                    "maxmem": 1073741824,
                    "cpus": 1,
                    "mem": 536870912,
                    "cpu": 0.10,
                    "maxdisk": 21474836480,
                    "disk": 1125899906,
                    "uptime": 86400,
                },
            },
        ),
    }

    coordinator = mock_config_entry.runtime_data
    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
