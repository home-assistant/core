"""Base classes for Renault entities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from homeassistant.const import ATTR_NAME
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .renault_coordinator import RenaultDataUpdateCoordinator, T
from .renault_vehicle import RenaultVehicleProxy


@dataclass
class RenaultDataRequiredKeysMixin:
    """Mixin for required keys."""

    coordinator: str


@dataclass
class RenaultDataEntityDescription(EntityDescription, RenaultDataRequiredKeysMixin):
    """Class describing Renault data entities."""


class RenaultEntity(Entity):
    """Implementation of a Renault entity with a data coordinator."""

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

    @property
    def name(self) -> str:
        """Return the name of the entity.

        Overridden to include the device name.
        """
        return f"{self.vehicle.device_info[ATTR_NAME]} {self.entity_description.name}"


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
        if self.coordinator.data is None:
            return None  # type: ignore[unreachable]
        return cast(StateType, getattr(self.coordinator.data, key))
