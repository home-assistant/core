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

    async def _async_update_data(self) -> dict[int, BoundLoadBalancer]:
        """Fetch load balancers from Hetzner Cloud."""
        try:
            load_balancers = await self.hass.async_add_executor_job(
                self.client.load_balancers.get_all
            )
        except APIException as err:
            if err.code == 401:
                raise ConfigEntryAuthFailed(
                    f"Authentication failed: {err.message}"
                ) from err
            raise UpdateFailed(
                f"Error communicating with Hetzner Cloud API: {err.message}"
            ) from err

        return {
            lb.data_model.id: lb
            for lb in load_balancers
            if lb.data_model.id is not None
        }
