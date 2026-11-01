"""Base entity for E3/DC devices."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import E3dcDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class E3dcEntityDescription(EntityDescription):
    """Describe an E3/DC entity."""

    component: str  # attribute name on E3dcPowerStation, e.g. 'power'


class E3dcEntity(CoordinatorEntity[E3dcDataUpdateCoordinator]):
    """Defines a base E3/DC entity."""

    _attr_has_entity_name = True
    entity_description: E3dcEntityDescription

    def __init__(
        self,
        coordinator: E3dcDataUpdateCoordinator,
        entity_description: E3dcEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        serial = coordinator.config_entry.unique_id
        if TYPE_CHECKING:
            assert serial is not None
        self._attr_unique_id = f"{serial}_{entity_description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        return (
            super().available
            and self.entity_description.component not in self.coordinator.data.failed
        )
