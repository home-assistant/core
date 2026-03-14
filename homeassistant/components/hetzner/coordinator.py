"""Data update coordinator for the Hetzner Cloud integration."""

from __future__ import annotations

from dataclasses import dataclass

from hcloud import APIException, Client
from hcloud.load_balancers.client import BoundLoadBalancer

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, SCAN_INTERVAL


@dataclass
class HetznerData:
    """Runtime data for the Hetzner Cloud integration."""

    client: Client
    coordinator: HetznerCoordinator


type HetznerConfigEntry = ConfigEntry[HetznerData]


class HetznerCoordinator(DataUpdateCoordinator[dict[int, BoundLoadBalancer]]):
    """Hetzner Cloud data update coordinator."""

    config_entry: HetznerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HetznerConfigEntry,
        client: Client,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Hetzner Cloud",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.server_names: dict[int, str] = {}

    def _fetch_data(
        self,
    ) -> tuple[list[BoundLoadBalancer], dict[int, str]]:
        """Fetch load balancers and resolve server names.

        Runs in executor thread so blocking hcloud lazy loads are safe.
        """
        load_balancers = self.client.load_balancers.get_all()

        server_names: dict[int, str] = {}
        for lb in load_balancers:
            for target in lb.data_model.targets or []:
                if (
                    target.type == "server"
                    and target.server is not None
                    and target.server.id is not None
                ):
                    server_id = target.server.id
                    if server_id not in server_names:
                        try:
                            name = target.server.name
                        except APIException:
                            name = None
                        server_names[server_id] = name or str(server_id)

        return load_balancers, server_names

    async def _async_update_data(self) -> dict[int, BoundLoadBalancer]:
        """Fetch load balancers from Hetzner Cloud."""
        try:
            load_balancers, server_names = await self.hass.async_add_executor_job(
                self._fetch_data
            )
        except APIException as err:
            if err.code == 401:
                raise ConfigEntryAuthFailed(
                    f"Authentication failed: {err.message}"
                ) from err
            raise UpdateFailed(
                f"Error communicating with Hetzner Cloud API: {err.message}"
            ) from err

        self.server_names = server_names

        return {
            lb.data_model.id: lb
            for lb in load_balancers
            if lb.data_model.id is not None
        }
