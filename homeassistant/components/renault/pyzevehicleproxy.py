"""Proxy to handle account communication with Renault servers via PyZE."""
from datetime import timedelta
import logging

from pyze.api import Vehicle

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
LOGGER = logging.getLogger(__name__)


class PyzeVehicleProxy:
    """Handle vehicle communication with Renault servers via PyZE."""

    def __init__(self, hass, vehicle_link, pyze_vehicle: Vehicle):
        """Initialise vehicle proxy."""
        self.hass = hass
        self._vehicle_link = vehicle_link
        self._pyze_vehicle = pyze_vehicle
        self._device_info = None
        self.coordinators = {}
        self.async_initialise = self._async_initialise()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._device_info

    @property
    def registration(self):
        """Return the registration of the vehicle."""
        return self._vehicle_link["vehicleDetails"]["registrationNumber"]

    @property
    def vin(self):
        """Return the VIN of the vehicle."""
        return self._vehicle_link["vin"]

    async def _async_initialise(self):
        """Load available sensors."""
        brand = self._vehicle_link["brand"]
        model_label = self._vehicle_link["vehicleDetails"]["model"]["label"]
        registration_number = self._vehicle_link["vehicleDetails"]["registrationNumber"]
        model_code = self._vehicle_link["vehicleDetails"]["model"]["code"]
        self._device_info = {
            "identifiers": {(DOMAIN, self.vin)},
            "manufacturer": brand.capitalize(),
            "model": model_label.capitalize(),
            "name": registration_number,
            "sw_version": model_code,
        }

        self.coordinators["battery"] = DataUpdateCoordinator(
            self.hass,
            LOGGER,
            # Name of the data. For logging purposes.
            name=f"{self.vin} battery",
            update_method=self.get_battery_status,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        for key in self.coordinators:
            await self.coordinators[key].async_refresh()

    async def get_battery_status(self):
        """Get battery_status."""
        return await self.hass.async_add_executor_job(self._pyze_vehicle.battery_status)
