"""Base entity for De Dietrich devices."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from diematic_modbus import Diematic, DiematicISystem

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import DeDietrichDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class DeDietrichEntityDescription(EntityDescription):
    """Describe a De Dietrich entity."""

    component: (
        str  # attribute name on the device, e.g. 'sensors', 'hot_water', 'circuit_a'
    )
    exists_fn: Callable[[Diematic | DiematicISystem], bool] = lambda _: True


class DeDietrichEntity(CoordinatorEntity[DeDietrichDataUpdateCoordinator]):
    """Defines a base De Dietrich entity."""

    _attr_has_entity_name = True
    entity_description: DeDietrichEntityDescription

    def __init__(
        self,
        coordinator: DeDietrichDataUpdateCoordinator,
        entity_description: DeDietrichEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self._attr_device_info = coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        if not super().available:
            return False
        return self.entity_description.component not in self.coordinator.data.failed
