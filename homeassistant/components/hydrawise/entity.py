"""Base classes for Hydrawise entities."""

from typing import Any

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)


class HydrawiseEntity(CoordinatorEntity):
    """Entity class for Hydrawise devices."""

    _attr_attribution = "Data provided by hydrawise.com"

    def __init__(
        self,
        *,
        data: dict[str, Any],
        coordinator: DataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the Hydrawise entity."""
        super().__init__(coordinator=coordinator)
        self.data = data
        self.entity_description = description
        self._attr_name = f"{self.data['name']} {description.name}"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"identifier": self.data.get("relay")}
