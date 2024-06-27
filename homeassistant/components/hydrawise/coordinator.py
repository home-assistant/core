"""DataUpdateCoordinator for the Hydrawise integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from pydrawise import Hydrawise
from pydrawise.schema import Controller, ControllerWaterUseSummary, Sensor, User, Zone

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import now

from .const import DOMAIN, LOGGER


@dataclass
class HydrawiseData:
    """Container for data fetched from the Hydrawise API."""

    user: User
    controllers: dict[int, Controller]
    zones: dict[int, Zone]
    sensors: dict[int, Sensor]
    daily_water_summary: dict[int, ControllerWaterUseSummary]


class HydrawiseDataUpdateCoordinator(DataUpdateCoordinator[HydrawiseData]):
    """The Hydrawise Data Update Coordinator."""

    api: Hydrawise

    def __init__(
        self, hass: HomeAssistant, api: Hydrawise, scan_interval: timedelta
    ) -> None:
        """Initialize HydrawiseDataUpdateCoordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=scan_interval)
        self.api = api

    async def _async_update_data(self) -> HydrawiseData:
        """Fetch the latest data from Hydrawise."""
        # Don't fetch zones. We'll fetch them for each controller later.
        # This is to prevent 502 errors in some cases.
        # See: https://github.com/home-assistant/core/issues/120128
        user = await self.api.get_user(fetch_zones=False)
        controllers = {}
        zones = {}
        sensors = {}
        daily_water_summary: dict[int, ControllerWaterUseSummary] = {}
        for controller in user.controllers:
            controllers[controller.id] = controller
            controller.zones = await self.api.get_zones(controller)
            for zone in controller.zones:
                zones[zone.id] = zone
            for sensor in controller.sensors:
                sensors[sensor.id] = sensor
            daily_water_summary[controller.id] = await self.api.get_water_use_summary(
                controller,
                now().replace(hour=0, minute=0, second=0, microsecond=0),
                now(),
            )

        return HydrawiseData(
            user=user,
            controllers=controllers,
            zones=zones,
            sensors=sensors,
            daily_water_summary=daily_water_summary,
        )
