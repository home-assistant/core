"""Entity base for the Škoda integration."""

from skoda_public_api.models.active_ventilation import ActiveVentilation
from skoda_public_api.models.air_conditioning import AirConditioning
from skoda_public_api.models.auxiliary_heating import AuxiliaryHeating
from skoda_public_api.models.charging import Charging
from skoda_public_api.models.driving_range import FuelStatus
from skoda_public_api.models.parking_position import ParkingPosition
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
        self.vin = vin  # coordinator.vin
        self._attr_unique_id = f"{vin}_{self.entity_description.key}"

        vehicle_name = "Škoda Vehicle"
        if (
            coordinator.data
            and coordinator.data.vehicle_response
            and coordinator.data.vehicle_response.vehicle
        ):
            vehicle_name = (
                coordinator.data.vehicle_response.vehicle.name or f"Škoda {vin}"
            )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            name=vehicle_name,
            manufacturer="Škoda Auto",
            model=vehicle_name,
            serial_number=vin,
        )

    @property
    def open_api_vehicle(self) -> VehicleObject | None:
        """Returns main VehicleObject from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle
        return None

    @property
    def open_api_odometer(self) -> Odometer | None:
        """Returns main Odometer from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.odometer
        return None

    @property
    def open_api_air_conditioning(self) -> AirConditioning | None:
        """Returns main AirConditioning from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.air_conditioning
        return None

    @property
    def open_api_vehicle_status(self) -> VehicleStatus | None:
        """Returns main VehicleStatus from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.status
        return None

    @property
    def open_api_parking_position(self) -> ParkingPosition | None:
        """Returns main ParkingPosition from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.parking_position
        return None

    @property
    def open_api_driving_range(self) -> FuelStatus | None:
        """Returns main FuelStatus from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.fuel_status
        return None

    @property
    def open_api_charging(self) -> Charging | None:
        """Returns main Charging from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.charging
        return None

    @property
    def open_api_auxiliary_heating(self) -> AuxiliaryHeating | None:
        """Returns main AuxiliaryHeating from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.auxiliary_heating
        return None

    @property
    def open_api_active_ventilation(self) -> ActiveVentilation | None:
        """Returns main ActiveVentilation from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.active_ventilation
        return None
