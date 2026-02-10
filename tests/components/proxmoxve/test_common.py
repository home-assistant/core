"""Tests for Proxmox VE common module."""

from unittest.mock import MagicMock

from proxmoxer.core import ResourceException
import requests.exceptions

from homeassistant.components.proxmoxve.common import (
    call_api_container_vm,
    get_node_storages,
    parse_api_container_vm,
)
from homeassistant.components.proxmoxve.const import TYPE_CONTAINER, TYPE_VM


def test_parse_api_container_vm() -> None:
    """Test parsing VM/container API response."""
    status = {"status": "running", "name": "test-vm"}
    result = parse_api_container_vm(status)
    assert result == {"status": "running", "name": "test-vm"}


def test_call_api_container_vm_qemu(
    mock_proxmox_client: MagicMock,
) -> None:
    """Test call_api_container_vm for QEMU VM."""
    result = call_api_container_vm(mock_proxmox_client, "pve1", 100, TYPE_VM)
    assert result is not None
    assert result["status"] == "running"
    assert result["name"] == "vm-web"


def test_call_api_container_vm_lxc(
    mock_proxmox_client: MagicMock,
) -> None:
    """Test call_api_container_vm for LXC container."""
    result = call_api_container_vm(mock_proxmox_client, "pve1", 200, TYPE_CONTAINER)
    assert result is not None
    assert result["status"] == "running"
    assert result["name"] == "ct-nginx"


def test_call_api_container_vm_returns_none_on_resource_exception() -> None:
    """Test call_api_container_vm returns None on ResourceException."""
    node_mock = MagicMock()
    node_mock.qemu.return_value.status.current.get.side_effect = ResourceException(
        "404", "status", "content"
    )
    proxmox = MagicMock()
    proxmox.nodes.return_value = node_mock
    result = call_api_container_vm(proxmox, "pve1", 100, TYPE_VM)
    assert result is None


def test_get_node_storages(
    mock_proxmox_client: MagicMock,
) -> None:
    """Test get_node_storages returns list of storage info."""
    result = get_node_storages(mock_proxmox_client, "pve1")
    assert len(result) == 2
    storages = {s["storage"]: s for s in result}
    assert "local" in storages
    assert "local-lvm" in storages
    assert storages["local"]["type"] == "dir"
    assert storages["local"]["total"] == 500000000000
    assert storages["local"]["used"] == 100000000000
    assert storages["local"]["avail"] == 400000000000


def test_get_node_storages_returns_empty_on_connection_error(
    mock_proxmox_client: MagicMock,
) -> None:
    """Test get_node_storages returns empty list when storage.get() fails."""
    mock_proxmox_client.nodes.return_value.storage.get.side_effect = (
        requests.exceptions.ConnectionError()
    )
    result = get_node_storages(mock_proxmox_client, "pve1")
    assert result == []


def test_get_node_storages_returns_empty_on_resource_exception(
    mock_proxmox_client: MagicMock,
) -> None:
    """Test get_node_storages returns empty list when storage.get() raises ResourceException."""
    mock_proxmox_client.nodes.return_value.storage.get.side_effect = ResourceException(
        "500", "status", "content"
    )
    result = get_node_storages(mock_proxmox_client, "pve1")
    assert result == []


def test_get_node_storages_skips_storage_when_status_fails() -> None:
    """Test get_node_storages skips a storage when its status.get() fails."""
    node_mock = MagicMock()
    node_mock.storage.get.return_value = [
        {"storage": "local", "type": "dir"},
        {"storage": "broken", "type": "dir"},
    ]

    def storage_side_effect(storage_id: str) -> MagicMock:
        resource = MagicMock()
        if storage_id == "broken":
            resource.status.get.side_effect = ResourceException(
                "500", "status", "content"
            )
        else:
            resource.status.get.return_value = {
                "total": 100,
                "used": 50,
                "avail": 50,
            }
        return resource

    node_mock.storage.side_effect = storage_side_effect
    proxmox = MagicMock()
    proxmox.nodes.return_value = node_mock

    result = get_node_storages(proxmox, "pve1")
    assert len(result) == 1
    assert result[0]["storage"] == "local"
