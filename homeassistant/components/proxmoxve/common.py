"""Commons for Proxmox VE integration."""

from __future__ import annotations

from typing import Any

from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
import requests.exceptions

from .const import TYPE_CONTAINER, TYPE_VM


class ProxmoxClient:
    """A wrapper for the proxmoxer ProxmoxAPI client."""

    _proxmox: ProxmoxAPI

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        realm: str,
        password: str,
        verify_ssl: bool,
    ) -> None:
        """Initialize the ProxmoxClient."""

        self._host = host
        self._port = port
        self._user = user
        self._realm = realm
        self._password = password
        self._verify_ssl = verify_ssl

    def build_client(self) -> None:
        """Construct the ProxmoxAPI client.

        Allows inserting the realm within the `user` value.
        """

        if "@" in self._user:
            user_id = self._user
        else:
            user_id = f"{self._user}@{self._realm}"

        self._proxmox = ProxmoxAPI(
            self._host,
            port=self._port,
            user=user_id,
            password=self._password,
            verify_ssl=self._verify_ssl,
        )

    def get_api_client(self) -> ProxmoxAPI:
        """Return the ProxmoxAPI client."""
        return self._proxmox


def parse_api_container_vm(status: dict[str, Any]) -> dict[str, Any]:
    """Get the container or vm api data and return it formatted in a dictionary.

    It is implemented in this way to allow for more data to be added for sensors
    in the future.
    """

    return {"status": status["status"], "name": status["name"]}


def call_api_container_vm(
    proxmox: ProxmoxAPI,
    node_name: str,
    vm_id: int,
    machine_type: int,
) -> dict[str, Any] | None:
    """Make proper api calls."""
    status = None

    try:
        if machine_type == TYPE_VM:
            status = proxmox.nodes(node_name).qemu(vm_id).status.current.get()
        elif machine_type == TYPE_CONTAINER:
            status = proxmox.nodes(node_name).lxc(vm_id).status.current.get()
    except ResourceException, requests.exceptions.ConnectionError:
        return None

    return status


def get_node_storages(
    proxmox: ProxmoxAPI,
    node_name: str,
) -> list[dict[str, Any]]:
    """Get storage list with total, used and avail space for a node.

    Returns a list of dicts with keys: storage, type, total, used, avail (bytes).
    On API errors, skips failing storages and returns the rest; on total failure
    returns an empty list.
    """
    result: list[dict[str, Any]] = []
    try:
        storages = proxmox.nodes(node_name).storage.get()
    except ResourceException, requests.exceptions.ConnectionError:
        return result
    if not storages:
        return result
    for storage_info in storages:
        storage_id = storage_info.get("storage")
        if not storage_id:
            continue
        try:
            status = proxmox.nodes(node_name).storage(storage_id).status.get()
        except ResourceException, requests.exceptions.ConnectionError:
            continue
        total = status.get("total") or 0
        used = status.get("used") or 0
        avail = status.get("avail")
        if avail is None and total is not None and used is not None:
            avail = max(0, total - used)
        elif avail is None:
            avail = 0
        result.append(
            {
                "storage": storage_id,
                "type": storage_info.get("type", ""),
                "total": total,
                "used": used,
                "avail": avail,
            }
        )
    return result
