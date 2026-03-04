"""Tests for VM/container live migration between Proxmox nodes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.proxmoxve.coordinator import ProxmoxNodeData
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

import datetime


async def test_vm_migration_updates_entity(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a VM migrated to another node keeps entities working."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    # Verify VM 100 entity is available on pve1
    state = hass.states.get("sensor.vm_web_status")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Access the coordinator directly
    coordinator = mock_config_entry.runtime_data
    assert coordinator.get_vm_node(100) == "pve1"

    # Simulate migration: VM 100 moves from pve1 to pve2.
    # Build new coordinator data where VM 100 is now on pve2.
    migrated_vm = {
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
    }

    new_data = {
        "pve1": ProxmoxNodeData(
            node={"id": "node/pve1", "node": "pve1"},
            vms={
                # VM 100 is gone from pve1, only VM 101 remains
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
            node={"id": "node/pve2", "node": "pve2"},
            vms={
                # VM 100 has migrated here
                100: migrated_vm,
            },
            containers={},
        ),
    }

    # Directly update coordinator data to simulate a refresh after migration.
    coordinator._rebuild_id_maps(new_data)
    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    # VM 100 should now be resolved on pve2
    assert coordinator.get_vm_node(100) == "pve2"
    assert coordinator.get_vm_node(101) == "pve1"

    # Entity should still be available (not unavailable)
    state = hass.states.get("sensor.vm_web_status")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_container_migration_updates_entity(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a container migrated to another node keeps entities working."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.get_container_node(200) == "pve1"

    # Simulate migration: container 200 moves from pve1 to pve2.
    new_data = {
        "pve1": ProxmoxNodeData(
            node={"id": "node/pve1", "node": "pve1"},
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
                # Container 200 is gone, only 201 remains
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
            node={"id": "node/pve2", "node": "pve2"},
            vms={},
            containers={
                # Container 200 has migrated here
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

    coordinator._rebuild_id_maps(new_data)
    coordinator.async_set_updated_data(new_data)
    await hass.async_block_till_done()

    # Container 200 should now be resolved on pve2
    assert coordinator.get_container_node(200) == "pve2"
    assert coordinator.get_container_node(201) == "pve1"

    state = hass.states.get("sensor.ct_nginx_status")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_coordinator_id_maps_rebuilt_on_refresh(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that _vmid_to_node and _ctid_to_node are populated after setup."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data

    # Maps should be populated from initial data
    assert coordinator._vmid_to_node == {100: "pve1", 101: "pve1"}
    assert coordinator._ctid_to_node == {200: "pve1", 201: "pve1"}

    # O(1) lookups should work
    assert coordinator.get_vm_node(100) == "pve1"
    assert coordinator.get_vm_node(999) is None
    assert coordinator.get_container_node(200) == "pve1"
    assert coordinator.get_container_node(999) is None
