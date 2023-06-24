"""DataUpdateCoordinator for the Hydrawise integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL
from .hydrawiser import Hydrawiser


class HydrawiseDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """The Hydrawise Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, api: Hydrawiser) -> None:
        """Initialize HydrawiseDataUpdateCoordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = api

    async def _async_update_data(self) -> None:
        """Fetch the latest data from Hydrawise."""
        result = await self.api.async_update_controllers()
        if not result:
            raise UpdateFailed("Failed to refresh Hydrawise data")


class HydrawiseEntity(CoordinatorEntity[HydrawiseDataUpdateCoordinator]):
    """Entity class for Hydrawise devices."""

    _attr_attribution = "Data provided by hydrawise.com"
    controller_id: int
    zone_id: int

    def __init__(
        self,
        *,
        coordinator: HydrawiseDataUpdateCoordinator,
        controller_id: int,
        zone_id: int,
        description: EntityDescription,
    ) -> None:
        """Initialize the Hydrawise entity."""
        super().__init__(coordinator=coordinator)
        self.controller_id = controller_id
        self.zone_id = zone_id
        self._attr_unique_id = f"{self.controller_id}_{self.zone_id}_{description.key}"
        self.entity_description = description
        controller = coordinator.api.get_controller(self.controller_id)
        if controller is None:
            raise TypeError("Unable to initialize controller")

        zone = coordinator.api.get_zone(self.zone_id)
        if zone is None:
            self._attr_name = f"{controller.name} {description.name}"
        else:
            self._attr_name = f"{zone.name} {description.name}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.controller_id))},
            name=controller.name,
            manufacturer="Hunter HydraWise",
        )
