"""Tests for Proxmox VE services."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.proxmoxve.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration

SERVICE_VM_COMMAND_WAIT = "vm_command_wait"


async def test_vm_command_wait_success(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry,
) -> None:
    """Test waiting for a successful VM command task."""
    await setup_integration(hass, mock_config_entry)

    resource = mock_proxmox_client._node_mock.qemu(100)
    resource.status.start.post.return_value = "UPID:qemu-start"
    mock_proxmox_client._node_mock.tasks.return_value.status.get.side_effect = [
        {"status": "running"},
        {"status": "stopped", "exitstatus": "OK"},
    ]

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_VM_COMMAND_WAIT,
        {
            "node": "pve1",
            "vmid": 100,
            "resource_type": "qemu",
            "command": "start",
            "poll_interval": 0.2,
        },
        blocking=True,
        return_response=True,
    )

    assert response == {
        "command": "start",
        "entry_id": mock_config_entry.entry_id,
        "exitstatus": "OK",
        "node": "pve1",
        "resource_type": "qemu",
        "status": "stopped",
        "upid": "UPID:qemu-start",
        "vmid": 100,
    }


async def test_vm_command_wait_task_failure(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry,
) -> None:
    """Test surfacing a failed VM command task."""
    await setup_integration(hass, mock_config_entry)

    resource = mock_proxmox_client._node_mock.qemu(100)
    resource.status.start.post.return_value = "UPID:qemu-start"
    mock_proxmox_client._node_mock.tasks.return_value.status.get.return_value = {
        "status": "stopped",
        "exitstatus": "ERROR",
    }

    with pytest.raises(
        HomeAssistantError,
        match="failed with exit status 'ERROR'",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_VM_COMMAND_WAIT,
            {
                "node": "pve1",
                "vmid": 100,
                "resource_type": "qemu",
                "command": "start",
            },
            blocking=True,
            return_response=True,
        )


async def test_vm_command_wait_permission_denied(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry,
) -> None:
    """Test validating VM power permissions before starting a task."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_VM_COMMAND_WAIT,
            {
                "node": "pve1",
                "vmid": 101,
                "resource_type": "qemu",
                "command": "start",
            },
            blocking=True,
            return_response=True,
        )
