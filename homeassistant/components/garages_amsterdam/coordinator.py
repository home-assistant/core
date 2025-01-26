"""Coordinator for the Garages Amsterdam integration."""

from __future__ import annotations

from odp_amsterdam import Garage, ODPAmsterdam, VehicleType

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


class GaragesAmsterdamDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Garage]]):
    """Class to manage fetching Garages Amsterdam data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ODPAmsterdam,
    ) -> None:
        """Initialize global Garages Amsterdam data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Garage]:
        return {
            garage.garage_name: garage
            for garage in await self.client.all_garages(vehicle=VehicleType.CAR)
        }
