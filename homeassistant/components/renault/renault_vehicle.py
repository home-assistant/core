"""Proxy to handle account communication with Renault servers."""
from datetime import timedelta
import logging
from typing import Any, Dict

from renault_api.kamereon.models import (
    KamereonVehicleCockpitData,
    KamereonVehiclesDetails,
)
from renault_api.renault_vehicle import RenaultVehicle

from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN
from .renault_coordinator import RenaultDataUpdateCoordinator

DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

LOGGER = logging.getLogger(__name__)


class RenaultVehicleProxy:
    """Handle vehicle communication with Renault servers."""

    def __init__(
        self,
        hass: HomeAssistantType,
        vehicle: RenaultVehicle,
        details: KamereonVehiclesDetails,
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

    @property
    def details(self) -> KamereonVehiclesDetails:
        """Return the specs of the vehicle."""
        return self._details

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return a device description for device registry."""
        return self._device_info

    async def async_initialise(self) -> None:
        """Load available sensors."""
        self.coordinators["cockpit"] = RenaultDataUpdateCoordinator(
            self.hass,
            LOGGER,
            # Name of the data. For logging purposes.
            name=f"{self.details.vin} cockpit",
            update_method=self.get_cockpit,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        for key in list(self.coordinators.keys()):
            await self.coordinators[key].async_refresh()
            if self.coordinators[key].not_supported:
                # Remove endpoint if it is not supported for this vehicle.
                del self.coordinators[key]
            elif self.coordinators[key].access_denied:
                # Remove endpoint if it is denied for this vehicle.
                del self.coordinators[key]

    async def get_cockpit(self) -> KamereonVehicleCockpitData:
        """Get cockpit."""
        return await self._vehicle.get_cockpit()
