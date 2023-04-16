"""DataUpdateCoordinators for the Proxmox VE integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from proxmoxer import AuthenticationError, ProxmoxAPI
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, UPDATE_INTERVAL
from .models import ProxmoxVMData


class ProxmoxCoordinator(DataUpdateCoordinator[ProxmoxVMData]):
    """Proxmox VE data update coordinator."""


class ProxmoxQEMUCoordinator(ProxmoxCoordinator):
    """Proxmox VE QEMU data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        proxmox: ProxmoxAPI,
        host_name: str,
        node_name: str,
        qemu_id: int,
    ) -> None:
        """Initialize the Proxmox QEMU coordinator."""

        super().__init__(
            hass,
            LOGGER,
            name=f"proxmox_coordinator_{host_name}_{node_name}_{qemu_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

        self.hass = hass
        self.proxmox = proxmox
        self.node_name = node_name
        self.qemu_id = qemu_id

    async def _async_update_data(self) -> ProxmoxVMData:
        """Update data  for Proxmox QEMU."""

        def poll_api() -> dict[str, Any] | None:
            """Return data from the Proxmox QEMU API."""
            try:
                api_status = (
                    self.proxmox.nodes(self.node_name)
                    .qemu(self.qemu_id)
                    .status.current.get()
                )

            except (
                AuthenticationError,
                SSLError,
                ConnectTimeout,
                ResourceException,
            ) as error:
                raise UpdateFailed from error
            LOGGER.debug("API Response: %s", api_status)
            return api_status

        api_status = await self.hass.async_add_executor_job(poll_api)
        if api_status is None:
            raise UpdateFailed(
                f"Vm/Container {self.qemu_id} unable to be found in node {self.node_name}"
            )

        return ProxmoxVMData(
            status=api_status["status"],
            name=api_status["name"],
        )


class ProxmoxLXCCoordinator(ProxmoxCoordinator):
    """Proxmox VE LXC data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        proxmox: ProxmoxAPI,
        host_name: str,
        node_name: str,
        container_id: int,
    ) -> None:
        """Initialize the Proxmox LXC coordinator."""

        super().__init__(
            hass,
            LOGGER,
            name=f"proxmox_coordinator_{host_name}_{node_name}_{container_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

        self.hass = hass
        self.proxmox = proxmox
        self.node_name = node_name
        self.container_id = container_id

    async def _async_update_data(self) -> ProxmoxVMData:
        """Update data  for Proxmox LXC."""

        def poll_api() -> dict[str, Any] | None:
            """Return data from the Proxmox LXC API."""
            try:
                api_status = (
                    self.proxmox.nodes(self.node_name)
                    .lxc(self.container_id)
                    .status.current.get()
                )

            except (
                AuthenticationError,
                SSLError,
                ConnectTimeout,
                ResourceException,
            ) as error:
                raise UpdateFailed from error
            LOGGER.debug("API Response: %s", api_status)
            return api_status

        api_status = await self.hass.async_add_executor_job(poll_api)
        if api_status is None:
            raise UpdateFailed(
                f"Vm/Container {self.container_id} unable to be found in node {self.node_name}"
            )

        return ProxmoxVMData(
            status=api_status["status"],
            name=api_status["name"],
        )
