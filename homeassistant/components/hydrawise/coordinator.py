"""DataUpdateCoordinator for the Hydrawise integration."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydrawise import Hydrawise
from pydrawise.schema import Controller, ControllerWaterUseSummary, Sensor, User, Zone

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import now

from .const import DOMAIN, LOGGER, MAIN_SCAN_INTERVAL, WATER_USE_SCAN_INTERVAL


@dataclass
class HydrawiseData:
    """Container for data fetched from the Hydrawise API."""

    user: User
    controllers: dict[int, Controller] = field(default_factory=dict)
    zones: dict[int, Zone] = field(default_factory=dict)
    sensors: dict[int, Sensor] = field(default_factory=dict)
    daily_water_summary: dict[int, ControllerWaterUseSummary] = field(
        default_factory=dict
    )


@dataclass
class HydrawiseUpdateCoordinators:
    """Container for all Hydrawise DataUpdateCoordinator instances."""

    main: HydrawiseMainDataUpdateCoordinator
    water_use: HydrawiseWaterUseDataUpdateCoordinator


class HydrawiseDataUpdateCoordinator(DataUpdateCoordinator[HydrawiseData]):
    """Base class for Hydrawise Data Update Coordinators."""

    api: Hydrawise


class HydrawiseMainDataUpdateCoordinator(HydrawiseDataUpdateCoordinator):
    """The main Hydrawise Data Update Coordinator.

    This fetches the primary state data for Hydrawise controllers and zones
    at a relatively frequent interval so that the primary functions of the
    integration are updated in a timely manner.
    """

    def __init__(self, hass: HomeAssistant, api: Hydrawise) -> None:
        """Initialize HydrawiseDataUpdateCoordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=MAIN_SCAN_INTERVAL)
        self.api = api

    async def _async_update_data(self) -> HydrawiseData:
        """Fetch the latest data from Hydrawise."""
        # Don't fetch zones. We'll fetch them for each controller later.
        # This is to prevent 502 errors in some cases.
        # See: https://github.com/home-assistant/core/issues/120128
        data = HydrawiseData(user=await self.api.get_user(fetch_zones=False))
        for controller in data.user.controllers:
            data.controllers[controller.id] = controller
            controller.zones = await self.api.get_zones(controller)
            for zone in controller.zones:
                data.zones[zone.id] = zone
            for sensor in controller.sensors:
                data.sensors[sensor.id] = sensor
        return data


class HydrawiseWaterUseDataUpdateCoordinator(HydrawiseDataUpdateCoordinator):
    """Data Update Coordinator for Hydrawise Water Use.

    This fetches data that is more expensive for the Hydrawise API to compute
    at a less frequent interval as to not overload the Hydrawise servers.
    """

    _main_coordinator: HydrawiseMainDataUpdateCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        api: Hydrawise,
        main_coordinator: HydrawiseMainDataUpdateCoordinator,
    ) -> None:
        """Initialize HydrawiseWaterUseDataUpdateCoordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN} water use",
            update_interval=WATER_USE_SCAN_INTERVAL,
        )
        self.api = api
        self._main_coordinator = main_coordinator

    async def _async_update_data(self) -> HydrawiseData:
        """Fetch the latest data from Hydrawise."""
        daily_water_summary: dict[int, ControllerWaterUseSummary] = {}
        for controller in self._main_coordinator.data.controllers.values():
            daily_water_summary[controller.id] = await self.api.get_water_use_summary(
                controller,
                now().replace(hour=0, minute=0, second=0, microsecond=0),
                now(),
            )
        main_data = self._main_coordinator.data
        return HydrawiseData(
            user=main_data.user,
            controllers=main_data.controllers,
            zones=main_data.zones,
            sensors=main_data.sensors,
            daily_water_summary=daily_water_summary,
        )
