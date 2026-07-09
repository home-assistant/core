"""Base entity for the Fronius integration."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from .coordinator import FroniusCoordinatorBase


@dataclass(frozen=True)
class FroniusEntityDescription(EntityDescription):
    """Base class for Fronius entity descriptions."""

    response_key: str | None = None


class FroniusEntity(CoordinatorEntity["FroniusCoordinatorBase"]):
    """Defines a Fronius coordinator entity."""

    entity_description: FroniusEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FroniusCoordinatorBase,
        description: FroniusEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius coordinator entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.response_key = description.response_key or description.key
        self.solar_net_id = solar_net_id
        self._attr_translation_key = description.translation_key or description.key

    def _device_data(self) -> dict[str, Any]:
        """Extract information for SolarNet device from coordinator data."""
        return self.coordinator.data[self.solar_net_id]
