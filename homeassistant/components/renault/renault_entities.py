"""Base classes for Renault entities."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, cast

from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import as_utc, parse_datetime

from .renault_coordinator import T
from .renault_vehicle import RenaultVehicleProxy


@dataclass
class RenaultRequiredKeysMixin:
    """Mixin for required keys."""

    coordinator: str


@dataclass
class RenaultEntityDescription(EntityDescription, RenaultRequiredKeysMixin):
    """Class describing Renault entities."""


ATTR_LAST_UPDATE = "last_update"


class RenaultDataEntity(CoordinatorEntity[Optional[T]], Entity):
    """Implementation of a Renault entity with a data coordinator."""

    entity_description: RenaultEntityDescription

    def __init__(
        self,
        vehicle: RenaultVehicleProxy,
        description: RenaultEntityDescription,
    ) -> None:
        """Initialise entity."""
        super().__init__(vehicle.coordinators[description.coordinator])
        self.vehicle = vehicle
        self.entity_description = description
        self._attr_device_info = self.vehicle.device_info
        self._attr_unique_id = f"{self.vehicle.details.vin}_{description.key}".lower()

    def _get_data_attr(self, key: str) -> StateType:
        """Return the attribute value from the coordinator data."""
        if self.coordinator.data is None:
            return None
        return cast(StateType, getattr(self.coordinator.data, key))

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of this entity."""
        last_update: str | None = None
        if self.entity_description.coordinator == "battery":
            last_update = cast(str, self._get_data_attr("timestamp"))
        elif self.entity_description.coordinator == "location":
            last_update = cast(str, self._get_data_attr("lastUpdateTime"))
        if last_update:
            return {ATTR_LAST_UPDATE: _convert_to_utc_string(last_update)}
        return None


def _convert_to_utc_string(value: str) -> str:
    """Convert date to UTC iso format."""
    original_dt = parse_datetime(value)
    if TYPE_CHECKING:
        assert original_dt is not None
    return as_utc(original_dt).isoformat()
