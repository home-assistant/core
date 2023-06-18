"""DataUpdateCoordinator for the Hydrawise integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, LOGGER
from .hydrawiser import Hydrawiser


class HydrawiseDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """The Hydrawise Data Update Coordinator."""

    def __init__(
        self, hass: HomeAssistant, api: Hydrawiser, scan_interval: timedelta
    ) -> None:
        """Initialize HydrawiseDataUpdateCoordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=scan_interval)
        self.api = api

    async def _async_update_data(self) -> None:
        """Fetch the latest data from Hydrawise."""
        result = await self.hass.async_add_executor_job(self.api.update_controllers)
        if not result:
            raise UpdateFailed("Failed to refresh Hydrawise data")


class HydrawiseEntity(CoordinatorEntity[HydrawiseDataUpdateCoordinator]):
    """Entity class for Hydrawise devices."""

    _attr_attribution = "Data provided by hydrawise.com"
    controller_id: int
    relay_id: int

    def __init__(
        self,
        *,
        coordinator: HydrawiseDataUpdateCoordinator,
        controller_id: int,
        relay_id: int,
        description: EntityDescription,
    ) -> None:
        """Initialize the Hydrawise entity."""
        super().__init__(coordinator=coordinator)
        self.controller_id = controller_id
        self.relay_id = relay_id
        self._attr_unique_id = f"{self.controller_id}_{self.relay_id}_{description.key}"
        self.entity_description = description
        controller = coordinator.api.get_controller(self.controller_id)
        if controller is None:
            raise TypeError("Unable to initialize controller")

        relay = coordinator.api.get_relay(self.controller_id, self.relay_id)
        if relay is None:
            raise TypeError("Unable to initialize relay")

        self._attr_name = f"{relay.name} {description.name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.controller_id))},
            name=controller.name,
            manufacturer="Hunter HydraWise",
        )
