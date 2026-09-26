"""Entity base for the Škoda integration."""

from skoda_public_api.models.air_conditioning import AirConditioning
from skoda_public_api.models.auxiliary_heating import AuxiliaryHeating
from skoda_public_api.models.charging import Charging
from skoda_public_api.models.driving_range import FuelStatus
from skoda_public_api.models.vehicle import Odometer, VehicleObject
from skoda_public_api.models.vehicle_status import VehicleStatus

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SkodaUpdateCoordinator


class SkodaEntity(CoordinatorEntity[SkodaUpdateCoordinator]):
    """Class for all the entities in the integration."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SkodaUpdateCoordinator, vin: str) -> None:
        """Initialize the entity with a unique ID based on VIN and entity key."""
        super().__init__(coordinator)
        self.vin = vin
        self._attr_unique_id = f"{vin}_{self.entity_description.key}"

        vehicle_name = coordinator.data.vehicle_response.vehicle.name or (
            f"Škoda {vin}"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            name=vehicle_name,
            manufacturer="Škoda Auto",
            model=vehicle_name,
            serial_number=vin,
        )

    @property
    def open_api_vehicle(self) -> VehicleObject:
        """Returns main VehicleObject from new OpenAPI."""
        return self.coordinator.data.vehicle_response.vehicle

    @property
    def open_api_odometer(self) -> Odometer | None:
        """Returns main Odometer from new OpenAPI."""
        return self.coordinator.data.vehicle_response.vehicle.odometer

    @property
    def open_api_air_conditioning(self) -> AirConditioning | None:
        """Returns main AirConditioning from new OpenAPI."""
        return self.coordinator.data.vehicle_response.vehicle.air_conditioning

    @property
    def open_api_vehicle_status(self) -> VehicleStatus | None:
        """Returns main VehicleStatus from new OpenAPI."""
        return self.coordinator.data.vehicle_response.vehicle.status

    @property
    def open_api_driving_range(self) -> FuelStatus | None:
        """Returns main FuelStatus from new OpenAPI."""
        return self.coordinator.data.vehicle_response.vehicle.fuel_status

    @property
    def open_api_charging(self) -> Charging | None:
        """Returns main Charging from new OpenAPI."""
        return self.coordinator.data.vehicle_response.vehicle.charging

    @property
    def open_api_auxiliary_heating(self) -> AuxiliaryHeating | None:
        """Returns main AuxiliaryHeating from new OpenAPI."""
        return self.coordinator.data.vehicle_response.vehicle.auxiliary_heating
