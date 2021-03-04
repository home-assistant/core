"""Proxy to handle account communication with Renault servers."""
from datetime import timedelta
import logging
from typing import Any, Dict

from renault_api.kamereon import models
from renault_api.renault_vehicle import RenaultVehicle

from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN
from .renault_coordinator import RenaultDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


class RenaultVehicleProxy:
    """Handle vehicle communication with Renault servers."""

    def __init__(
        self,
        hass: HomeAssistantType,
        vehicle: RenaultVehicle,
        details: models.KamereonVehicleDetails,
        scan_interval: timedelta,
    ) -> None:
        """Initialise vehicle proxy."""
        self.hass = hass
        self._vehicle = vehicle
        self._details = details
        self._device_info = {
            "identifiers": {(DOMAIN, details.vin)},
            "manufacturer": details.get_brand_label().capitalize(),
            "model": details.get_model_label().capitalize(),
            "name": details.registrationNumber,
            "sw_version": details.get_model_code(),
        }
        self.coordinators: Dict[str, RenaultDataUpdateCoordinator] = {}
        self.hvac_target_temperature = 21
        self._scan_interval = scan_interval

    @property
    def details(self) -> models.KamereonVehicleDetails:
        """Return the specs of the vehicle."""
        return self._details

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return a device description for device registry."""
        return self._device_info

    async def async_initialise(self) -> None:
        """Load available sensors."""
        if await self.endpoint_available("cockpit"):
            self.coordinators["cockpit"] = RenaultDataUpdateCoordinator(
                self.hass,
                LOGGER,
                # Name of the data. For logging purposes.
                name=f"{self.details.vin} cockpit",
                update_method=self.get_cockpit,
                # Polling interval. Will only be polled if there are subscribers.
                update_interval=self._scan_interval,
            )
        for key in list(self.coordinators.keys()):
            await self.coordinators[key].async_refresh()
            if self.coordinators[key].not_supported:
                # Remove endpoint if it is not supported for this vehicle.
                del self.coordinators[key]
            elif self.coordinators[key].access_denied:
                # Remove endpoint if it is denied for this vehicle.
                del self.coordinators[key]

    async def endpoint_available(self, endpoint: str) -> bool:
        """Ensure the endpoint is available to avoid unnecessary queries."""
        if not await self._vehicle.supports_endpoint(endpoint):
            return False
        if not await self._vehicle.has_contract_for_endpoint(endpoint):
            return False
        return True

    async def get_cockpit(self) -> models.KamereonVehicleCockpitData:
        """Get cockpit information from vehicle."""
        return await self._vehicle.get_cockpit()
