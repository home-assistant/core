from __future__ import annotations

from datetime import datetime

from intellifire4py import IntellifirePollData

from homeassistant.components.intellifire import IntellifireDataUpdateCoordinator
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class IntellifireEntityDescription(EntityDescription):
    """mixing with class."""


@dataclass
class IntellifireEntity(CoordinatorEntity):
    """Define a generic class for Intellifire entities."""

    coordinator: IntellifireDataUpdateCoordinator
    _attr_attribution = "Data provided by unpublished Intellifire API"

    def __init__(
            self,
            coordinator: IntellifireDataUpdateCoordinator,
            description: EntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description

        # Set the Display name the User will see
        self._attr_name = f"Fireplace {description.name}"
        self._attr_unique_id = f"{description.key}_{coordinator.api.data.serial}"
        # Configure the Device Info
        self._attr_device_info = self.coordinator.device_info
