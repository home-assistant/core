"""Platform for shared base classes for sensors."""
from __future__ import annotations

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FlumeNotificationDataUpdateCoordinator


class FlumeEntity(CoordinatorEntity[FlumeNotificationDataUpdateCoordinator]):
    """Base entity class."""

    _attr_attribution = "Data provided by Flume API"

    def __init__(
        self,
        coordinator: FlumeNotificationDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)

        self.entity_description = description
        self._attr_name = f"{description.name}"
        self._attr_unique_id = f"{description.key}"
