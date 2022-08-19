"""Platform for shared base classes for sensors."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FlumeDataUpdateCoordinator


class FlumeEntity(CoordinatorEntity[FlumeDataUpdateCoordinator]):
    """Base entity class."""

    _attr_attribution = "Data provided by Flume API"

    def __init__(
        self,
        coordinator: FlumeDataUpdateCoordinator,
        description: EntityDescription,
        name: str,
        device_id: str,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)

        self.device_id = device_id  # This is wrong
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{description.key}_{device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Flume, Inc.",
            model="Flume Smart Water Monitor",
            name=f"Flume {device_id}",
            configuration_url="https://portal.flumewater.com",
        )

    async def async_added_to_hass(self):
        """Request an update when added."""
        await super().async_added_to_hass()
        # We do not ask for an update with async_add_entities()
        # because it will update disabled entities
        await self.coordinator.async_request_refresh()
