"""Entity base for the Škoda integration."""

from collections.abc import Awaitable, Callable
from typing import Any

from skoda_public_api.api_layer.exceptions import OpenApiError, OpenApiRateLimitError
from skoda_public_api.api_layer.open_api_client import OpenAPIClient
from skoda_public_api.models.air_conditioning import AirConditioning
from skoda_public_api.models.auxiliary_heating import AuxiliaryHeating
from skoda_public_api.models.charging import Charging
from skoda_public_api.models.driving_range import FuelStatus
from skoda_public_api.models.vehicle import Odometer, VehicleObject

from homeassistant.exceptions import HomeAssistantError
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

    async def async_send_command(
        self, command: Callable[[OpenAPIClient, str], Awaitable[Any]]
    ) -> None:
        """Send a command to the vehicle."""
        try:
            await command(self.coordinator.openapi, self.vin)
        except OpenApiRateLimitError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="rate_limit_exceeded"
            ) from err
        except OpenApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

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
