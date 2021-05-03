"""Proxy to handle account communication with Renault servers."""
from __future__ import annotations

from datetime import timedelta
import logging

from renault_api.kamereon import models
from renault_api.renault_vehicle import RenaultVehicle

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .renault_coordinator import RenaultDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


class RenaultVehicleProxy:
    """Handle vehicle communication with Renault servers."""

    def __init__(
        self,
        hass: HomeAssistant,
        vehicle: RenaultVehicle,
        details: models.KamereonVehicleDetails,
        scan_interval: timedelta,
    ) -> None:
        """Initialise vehicle proxy."""
        self.hass = hass
        self._vehicle = vehicle
        self._details = details
        self._device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, details.vin or "")},
            "manufacturer": (details.get_brand_label() or "").capitalize(),
            "model": (details.get_model_label() or "").capitalize(),
            "name": details.registrationNumber or "",
            "sw_version": details.get_model_code() or "",
        }
        self.coordinators: dict[str, RenaultDataUpdateCoordinator] = {}
        self.hvac_target_temperature = 21
        self._scan_interval = scan_interval

    @property
    def details(self) -> models.KamereonVehicleDetails:
        """Return the specs of the vehicle."""
        return self._details

    @property
    def device_info(self) -> DeviceInfo:
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
        return await self._vehicle.supports_endpoint(
            endpoint
        ) and await self._vehicle.has_contract_for_endpoint(endpoint)

    async def get_cockpit(self) -> models.KamereonVehicleCockpitData:
        """Get cockpit information from vehicle."""
        return await self._vehicle.get_cockpit()
