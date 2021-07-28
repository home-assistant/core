"""Proxy to handle account communication with Renault servers."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import cast

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
            "identifiers": {(DOMAIN, cast(str, details.vin))},
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
        if await self.endpoint_available("hvac-status"):
            self.coordinators["hvac_status"] = RenaultDataUpdateCoordinator(
                self.hass,
                LOGGER,
                # Name of the data. For logging purposes.
                name=f"{self.details.vin} hvac_status",
                update_method=self.get_hvac_status,
                # Polling interval. Will only be polled if there are subscribers.
                update_interval=self._scan_interval,
            )
        if self.details.uses_electricity():
            if await self.endpoint_available("battery-status"):
                self.coordinators["battery"] = RenaultDataUpdateCoordinator(
                    self.hass,
                    LOGGER,
                    # Name of the data. For logging purposes.
                    name=f"{self.details.vin} battery",
                    update_method=self.get_battery_status,
                    # Polling interval. Will only be polled if there are subscribers.
                    update_interval=self._scan_interval,
                )
            if await self.endpoint_available("charge-mode"):
                self.coordinators["charge_mode"] = RenaultDataUpdateCoordinator(
                    self.hass,
                    LOGGER,
                    # Name of the data. For logging purposes.
                    name=f"{self.details.vin} charge_mode",
                    update_method=self.get_charge_mode,
                    # Polling interval. Will only be polled if there are subscribers.
                    update_interval=self._scan_interval,
                )
        # Check all coordinators
        await asyncio.gather(
            *(
                coordinator.async_config_entry_first_refresh()
                for coordinator in self.coordinators.values()
            )
        )
        for key in list(self.coordinators):
            # list() to avoid Runtime iteration error
            coordinator = self.coordinators[key]
            if coordinator.not_supported:
                # Remove endpoint as it is not supported for this vehicle.
                LOGGER.error(
                    "Ignoring endpoint %s as it is not supported for this vehicle: %s",
                    coordinator.name,
                    coordinator.last_exception,
                )
                del self.coordinators[key]
            elif coordinator.access_denied:
                # Remove endpoint as it is denied for this vehicle.
                LOGGER.error(
                    "Ignoring endpoint %s as it is denied for this vehicle: %s",
                    coordinator.name,
                    coordinator.last_exception,
                )
                del self.coordinators[key]

    async def endpoint_available(self, endpoint: str) -> bool:
        """Ensure the endpoint is available to avoid unnecessary queries."""
        return await self._vehicle.supports_endpoint(
            endpoint
        ) and await self._vehicle.has_contract_for_endpoint(endpoint)

    async def get_battery_status(self) -> models.KamereonVehicleBatteryStatusData:
        """Get battery status information from vehicle."""
        return await self._vehicle.get_battery_status()

    async def get_charge_mode(self) -> models.KamereonVehicleChargeModeData:
        """Get charge mode information from vehicle."""
        return await self._vehicle.get_charge_mode()

    async def get_cockpit(self) -> models.KamereonVehicleCockpitData:
        """Get cockpit information from vehicle."""
        return await self._vehicle.get_cockpit()

    async def get_hvac_status(self) -> models.KamereonVehicleHvacStatusData:
        """Get hvac status information from vehicle."""
        return await self._vehicle.get_hvac_status()
