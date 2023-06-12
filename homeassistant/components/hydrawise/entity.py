"""Base classes for Hydrawise entities."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HydrawiseDataUpdateCoordinator


class HydrawiseEntity(CoordinatorEntity[HydrawiseDataUpdateCoordinator]):
    """Entity class for Hydrawise devices."""

    _attr_attribution = "Data provided by hydrawise.com"

    def __init__(
        self,
        *,
        data: dict[str, Any],
        coordinator: HydrawiseDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the Hydrawise entity."""
        super().__init__(coordinator=coordinator)
        self.data = data
        self.entity_description = description
        self._attr_name = f"{self.data['name']} {description.name}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {"identifier": self.data.get("relay")}
