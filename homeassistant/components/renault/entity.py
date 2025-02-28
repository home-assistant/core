"""Base classes for Renault entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import RenaultDataUpdateCoordinator, T
from .renault_vehicle import RenaultVehicleProxy


@dataclass(frozen=True)
class RenaultDataRequiredKeysMixin:
    """Mixin for required keys."""

    coordinator: str


@dataclass(frozen=True)
class RenaultDataEntityDescription(EntityDescription, RenaultDataRequiredKeysMixin):
    """Class describing Renault data entities."""


class RenaultEntity(Entity):
    """Implementation of a Renault entity with a data coordinator."""

    _attr_has_entity_name = True
    entity_description: EntityDescription

    def __init__(
        self,
        vehicle: RenaultVehicleProxy,
        description: EntityDescription,
    ) -> None:
        """Initialise entity."""
        self.vehicle = vehicle
        self.entity_description = description
        self._attr_device_info = self.vehicle.device_info
        self._attr_unique_id = f"{self.vehicle.details.vin}_{description.key}".lower()


class RenaultDataEntity(
    CoordinatorEntity[RenaultDataUpdateCoordinator[T]], RenaultEntity
):
    """Implementation of a Renault entity with a data coordinator."""

    def __init__(
        self,
        vehicle: RenaultVehicleProxy,
        description: RenaultDataEntityDescription,
    ) -> None:
        """Initialise entity."""
        super().__init__(vehicle.coordinators[description.coordinator])
        RenaultEntity.__init__(self, vehicle, description)

    def _get_data_attr(self, key: str) -> StateType:
        """Return the attribute value from the coordinator data."""
        return cast(StateType, getattr(self.coordinator.data, key))
