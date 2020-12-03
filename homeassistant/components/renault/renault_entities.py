"""Base classes for Renault entities."""
from typing import Any, Dict

from renault_api.kamereon.models import KamereonVehicleCockpitData

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .renault_vehicle import RenaultVehicleProxy


class RenaultDataEntity(CoordinatorEntity, Entity):
    """Implementation of a Renault entity with a data coordinator."""

    def __init__(
        self, vehicle: RenaultVehicleProxy, entity_type: str, coordinator_key: str
    ) -> None:
        """Initialise entity."""
        super().__init__(vehicle.coordinators[coordinator_key])
        self.vehicle = vehicle
        self._entity_type = entity_type

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return a device description for device registry."""
        return self.vehicle.device_info

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this entity."""
        return slugify(f"{self.vehicle.details.vin}-{self._entity_type}")

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        return f"{self.vehicle.details.vin}-{self._entity_type}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Data can succeed, but be empty
        return self.coordinator.last_update_success and self.coordinator.data


class RenaultCockpitDataEntity(RenaultDataEntity):
    """Implementation of a Renault entity with cockpit coordinator."""

    def __init__(self, vehicle: RenaultVehicleProxy, entity_type: str) -> None:
        """Initialise entity."""
        super().__init__(vehicle, entity_type, "cockpit")

    @property
    def data(self) -> KamereonVehicleCockpitData:  # for type hints
        """Return collected data."""
        return self.coordinator.data
