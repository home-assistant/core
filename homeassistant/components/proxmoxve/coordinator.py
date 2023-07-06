"""Customized coordinator to manage Proxmox VE data."""
from datetime import timedelta
from typing import Any

from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
import requests

from homeassistant.components.proxmoxve.const import (
    _LOGGER,
    TYPE_CONTAINER,
    TYPE_VM,
    UPDATE_INTERVAL,
    StatusCommand,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


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


class ProxmoxDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage data from the Proxmox API."""

    def __init__(
        self,
        hass: HomeAssistant,
        proxmox_client: ProxmoxClient,
        host_name: str,
        node_name: str,
        vm_id: int,
        vm_type: int,
    ) -> None:
        """Initialize the data updater."""

        super().__init__(
            hass,
            _LOGGER,
            name=f"proxmox_coordinator_{host_name}_{node_name}_{vm_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

        self.proxmox_client = proxmox_client
        self.host_name = host_name
        self.node_name = node_name
        self.vm_id = vm_id
        self.vm_type = vm_type

    async def _async_update_data(self):
        """Get the container or vm api data and return it formatted in a dictionary."""

        vm_status = await self.get_vm_status()

        if vm_status is None:
            _LOGGER.warning(
                "Vm/Container %s unable to be found in node %s",
                self.vm_id,
                self.node_name,
            )
            return None

        return {"status": vm_status["status"], "name": vm_status["name"]}

    async def get_vm_status(self) -> dict[str, Any] | None:
        """Call GET {vm_id}/status/current."""

        status = None
        proxmox = self.proxmox_client.get_api_client()
        vm_type = self.vm_type
        node_name = self.node_name
        vm_id = self.vm_id

        try:
            if vm_type == TYPE_VM:
                status = await self.hass.async_add_executor_job(
                    proxmox.nodes(node_name).qemu(vm_id).status.current.get
                )
            elif vm_type == TYPE_CONTAINER:
                status = await self.hass.async_add_executor_job(
                    proxmox.nodes(node_name).lxc(vm_id).status.current.get
                )
        except (ResourceException, requests.exceptions.ConnectionError):
            return None

        return status

    async def set_vm_status(self, status_command: StatusCommand) -> None:
        """Call POST {vm_id}/status/{status_command}."""

        proxmox = self.proxmox_client.get_api_client()
        vm_type = self.vm_type
        node_name = self.node_name
        vm_id = self.vm_id

        try:
            if vm_type == TYPE_VM:
                await self.hass.async_add_executor_job(
                    proxmox.nodes(node_name)
                    .qemu(vm_id)
                    .status.__getattr__(status_command.value)
                    .create
                )
            elif vm_type == TYPE_CONTAINER:
                await self.hass.async_add_executor_job(
                    proxmox.nodes(node_name)
                    .lxc(vm_id)
                    .status.__getattr__(status_command.value)
                    .create
                )
        except (ResourceException, requests.exceptions.ConnectionError):
            raise HomeAssistantError("Call Proxmox API failed")

        self.async_refresh()
