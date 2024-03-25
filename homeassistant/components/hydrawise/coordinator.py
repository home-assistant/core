"""DataUpdateCoordinator for the Hydrawise integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from pydrawise import HydrawiseBase
from pydrawise.schema import Controller, User, Zone

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER


@dataclass
class HydrawiseData:
    """Container for data fetched from the Hydrawise API."""

    user: User
    controllers: dict[int, Controller]
    zones: dict[int, Zone]


class HydrawiseDataUpdateCoordinator(DataUpdateCoordinator[HydrawiseData]):
    """The Hydrawise Data Update Coordinator."""

    api: HydrawiseBase

    def __init__(
        self, hass: HomeAssistant, api: HydrawiseBase, scan_interval: timedelta
    ) -> None:
        """Initialize HydrawiseDataUpdateCoordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=scan_interval)
        self.api = api

    async def _async_update_data(self) -> HydrawiseData:
        """Fetch the latest data from Hydrawise."""
        user = await self.api.get_user()
        controllers = {}
        zones = {}
        for controller in user.controllers:
            controllers[controller.id] = controller
            for zone in controller.zones:
                zones[zone.id] = zone
        return HydrawiseData(user=user, controllers=controllers, zones=zones)
