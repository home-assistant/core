"""Tests for VM/container live migration between Proxmox nodes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.proxmoxve.coordinator import ProxmoxNodeData
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


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

    state = hass.states.get("sensor.vm_web_status")
    assert state is not None
    assert state.state == "running"

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

    state = hass.states.get("sensor.vm_web_status")
    assert state is not None
    assert state.state == "running"


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

    state = hass.states.get("sensor.ct_nginx_status")
    assert state is not None
    assert state.state == "running"

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

    state = hass.states.get("sensor.ct_nginx_status")
    assert state is not None
    assert state.state == "running"
